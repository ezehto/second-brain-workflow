"""The vault writer: the only code that creates files in the vault (plan sections 2.5, 2.9, 2.12).

P1-22 covers confinement, sanitising and atomic create from a template. P1-23 adds the edits of an
existing note: `set_frontmatter`, `set_status`, `append_to_section` and `fill_untouched` (2.2, 2.4).
The writer never touches the database; the indexer picks files up (or `index_single_file` is
called by the API).

Every target is resolved under the vault root: no `..`, no absolute path, no symlinked
component, no ignored path, only `.md`. Existence, uniqueness and emitted links are read from the
filesystem, never from the index.

Publishing never overwrites: the finished temp file is hard-linked to its final name (`os.link`
fails with EEXIST if the name is taken, in any letter case on the vault's drive) and the temp is
then unlinked. Where the filesystem refuses links (EPERM, ENOTSUP, EXDEV) it falls back to
`os.replace` after a last existence check, with a logged warning.

An edit is published by writing a temp file, re-reading and re-hashing the target immediately
before `os.replace` (a `ConflictError` if it no longer matches `expected_hash`), then replacing. The
window between that last check and the rename cannot be closed by any portable primitive; it is
the accepted residual risk of the design. Only the frontmatter block is rewritten by
`set_frontmatter`; the body bytes are never re-encoded. CRLF and a BOM are kept.

The frontmatter is round-tripped through ruamel, which keeps key order, comments and quotes but is
byte-stable only for Obsidian-shaped frontmatter. Other shapes are normalised on any edit: block
lists are re-indented to `  - item`, `~` and `null` are written as an empty value, `True` becomes
`true`, `+5` becomes `5`, flow collections get ruamel's spacing (`[a, b]`), a `"\\u00e9"` escape
is written as the character (the quotes stay), and mixed line endings in the block become the
file's first line ending. The meaning of every key is unchanged (the result is re-parsed and
checked).

Limits: a note over 5 MiB is not edited; a changed string value is at most 4 KiB, a list at most
256 items, a key at most 64 characters, the whole frontmatter block at most 64 KiB; the keys
`type`, `id` and `created` are never changed by `set_frontmatter`.

Errors, and the HTTP status the API (P1-28) maps them to; all derive from `WriterError`:

- `PathError`: 400
- `ConflictError`: 409
- `ValidationError`, `SanitizeError`, `TemplateError`: 422
- any other `OSError` is wrapped in a plain `WriterError` (500) with a vault-relative message.

For P1-28: the writer is safe against two writers creating the same name (exactly one wins), but
it takes no lock around an operation. A cross-worker advisory lock around each write operation
(so that ids, name checks and emitted links of concurrent operations cannot interleave) belongs to
the API layer.
"""

import errno
import hashlib
import io
import logging
import math
import os
import re
import secrets
import stat
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from django.utils import timezone
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.constructor import RoundTripConstructor
from ruamel.yaml.representer import RoundTripRepresenter

from vault import clock as vault_clock
from vault import conventions
from vault.ignore import is_ignored, iter_note_paths, read_sbignore
from vault.links import mask_code
from vault.parser import parse_note, split_frontmatter
from vault.sanitize import (
    SanitizeError,
    WriterError,
    is_reserved_name,
    sanitize_stem,
    utf16_length,
)
from vault.slug import project_note_slug, project_slug, resolve_project
from vault.templating import TemplateError, find_child_ci, load_template, render

__all__ = [
    "ConflictError",
    "CreatedNote",
    "EditResult",
    "NoteSpec",
    "PathError",
    "SanitizeError",
    "TemplateError",
    "ValidationError",
    "VaultWriter",
    "WriterError",
    "content_hash",
    "default_clock",
    "is_untouched",
]

logger = logging.getLogger(__name__)

MAX_PATH_LENGTH = 200  # UTF-16 units, vault-relative; keeps `D:\Second Brain\...` under 260 (2.5)
MAX_BODY_BYTES = 1024 * 1024
MAX_NOTES_PER_OPERATION = 50
MAX_IDS_PER_DAY = 86400
_LINK_FALLBACK_ERRNOS = (errno.EPERM, errno.ENOTSUP, errno.EXDEV)
_DIRECTORY_FSYNC_IGNORED_ERRNOS = (errno.EINVAL, errno.ENOTSUP)
CAPTURE_WORDS = 8
_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
_DRIVE_RE = re.compile(r"[A-Za-z]:")
_YEAR_FOLDER_RE = re.compile(r"\d{4}", re.ASCII)
_YAML_ESCAPED_CATEGORIES = ("Cc", "Cf", "Zl", "Zp")
_LINE_BREAK_CATEGORIES = ("Cc", "Zl", "Zp")  # refused in frontmatter keys and values (tab is fine)
MAX_NOTE_BYTES = 5 * 1024 * 1024  # a larger note is not edited
MAX_FRONTMATTER_STRING_BYTES = 4096
MAX_FRONTMATTER_LIST_ITEMS = 256
MAX_FRONTMATTER_BYTES = 64 * 1024
MAX_FRONTMATTER_KEY_LENGTH = 64
MAX_HEADING_LENGTH = 200
_FRONTMATTER_KEY_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9 _.-]*", re.ASCII)
_IDENTITY_KEYS = ("type", "id", "created")  # set_frontmatter never changes these
_ALLOWED_MARKERS = ("", "- ", "- [ ] ")
_LEADING_MARKER_RE = re.compile(r"[ \t]*(?:- \[[ xX]\] |- )")
_STRUCTURAL_LINE_RE = re.compile(r"[ \t>]*(?:#{1,6}(?:\s|$)|`{3,}|~{3,})")
_BOM = b"\xef\xbb\xbf"
_HEADING_RE = re.compile(r"(#{1,6}) +(.*)")
_FRONTMATTER_VALUE_TYPES = (str, int, float, bool, date, type(None))
_CHECKBOX_SECTIONS = frozenset({"today", "follow-ups"})  # daily-note sections that hold `- [ ]`


class PathError(WriterError):
    """A target escapes the vault, is ignored, is not a `.md` file, or sits in a folder the
    writer may not create (API: 400)."""


class ConflictError(WriterError):
    """A note with the same name (case-insensitive) exists in the folder (API: 409)."""


class _Touched(Exception):  # noqa: N818 - internal control flow of fill_untouched
    """The daily note differs from the template: leave it alone."""


class ValidationError(WriterError):
    """A field value is not allowed for the type, or a project cannot be resolved (API: 422)."""


@dataclass(frozen=True, slots=True)
class NoteSpec:
    """One note to create; `create` takes the same fields as keywords."""

    type: str
    title: str | None = None
    project: str | None = None
    priority: str | None = None
    due: str | date | None = None
    status: str | None = None
    body: str | None = None


@dataclass(frozen=True, slots=True)
class CreatedNote:
    """A created note: its vault-relative path (`/` separators), `id` and file name stem."""

    path: str
    note_id: str
    title: str
    type: str


@dataclass(frozen=True, slots=True)
class EditResult:
    """An edit: the note's path as it is spelled on disk, the SHA-256 of the file now on disk,
    whether a heading was added (`section_created`, 2.4 rule 6) and whether the file was written
    (`changed`; False when the edit would leave the bytes as they are, and when `fill_untouched`
    found the note touched; nothing is published then)."""

    path: str
    content_hash: str
    section_created: bool = False
    changed: bool = True


def content_hash(data: bytes) -> str:
    """The hash an edit's `expected_hash` is compared with: SHA-256 of the raw file bytes."""
    return hashlib.sha256(data).hexdigest()


def default_clock() -> datetime:
    """Pinned date in test mode (2.12) else today in TIME_ZONE, with the current time of day."""
    now = (
        timezone.localtime()
    )  # one clock read: the date and the time of day cannot straddle midnight
    return datetime.combine(
        vault_clock.pinned_date() or now.date(), now.time().replace(microsecond=0)
    )


class _Operation:
    """State shared by every note of one operation: one clock read, one directory walk."""

    def __init__(self, root: Path, now: datetime) -> None:
        self.root = root
        self.now = now.replace(microsecond=0)
        self.planned: list[str] = []  # paths created or about to be, in this operation
        self._walked: list[str] | None = None

    def at(self, index: int) -> datetime:
        """The note's timestamp: one second per earlier note, wrapping within the day (C20)."""
        if index >= MAX_IDS_PER_DAY:
            raise ValidationError("too many notes in one operation")
        seconds = self.now.hour * 3600 + self.now.minute * 60 + self.now.second + index
        seconds %= 86400
        return datetime.combine(
            self.now.date(), time(seconds // 3600, seconds % 3600 // 60, seconds % 60)
        )

    def note_paths(self) -> list[str]:
        """Non-ignored `.md` files on disk plus those planned in this operation."""
        if self._walked is None:
            self._walked = iter_note_paths(self.root)
        return [*self._walked, *self.planned]


def _exists_ci(directory: Path, name: str) -> bool:
    """True when `directory` holds an entry called `name` in any letter case (read from disk)."""
    folded = unicodedata.normalize("NFC", name).casefold()
    with os.scandir(directory) as scan:
        return any(unicodedata.normalize("NFC", e.name).casefold() == folded for e in scan)


def _describe(exc: OSError) -> str:
    """The error without any host path: `strerror` only."""
    return exc.strerror or type(exc).__name__


def _fsync_directory(directory: Path) -> None:
    """Make the new directory entry durable; never fails the create (drvfs refuses with EINVAL)."""
    try:
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        if exc.errno in _DIRECTORY_FSYNC_IGNORED_ERRNOS:
            logger.debug("directory fsync not supported here: %s", exc)
        else:
            logger.warning("directory fsync failed: %s", exc.strerror)


def _yaml_double_quoted(value: str) -> str:
    """A YAML double-quoted scalar; control, format and line-separator characters as \\uNNNN."""
    escaped = []
    for char in value:
        if char in '"\\':
            escaped.append("\\" + char)
        elif unicodedata.category(char) in _YAML_ESCAPED_CATEGORIES:
            escaped.append(f"\\u{ord(char):04x}")
        else:
            escaped.append(char)
    return '"' + "".join(escaped) + '"'


def _set_frontmatter(text: str, key: str, value: str, note_type: str) -> str:
    """Replace the template's `key:` line inside its frontmatter block."""
    lines = text.split("\n")
    if lines[0] == "---":
        end = next((i for i, line in enumerate(lines[1:], 1) if line in ("---", "...")), len(lines))
        for index in range(1, end):
            if re.match(rf"{re.escape(key)}:(\s|$)", lines[index]):
                lines[index] = f"{key}: {value}"
                return "\n".join(lines)
    raise ValidationError(f"a {note_type} note has no {key!r} key")


def _normalise_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


# --- Text edits (pure functions) ------------------------------------------------------------


class _Verbatim(str):
    """A scalar the YAML library cannot load as its implied type, kept as written."""

    tag: str


def _verbatim(node: Any) -> _Verbatim:
    value = _Verbatim(node.value)
    value.tag = node.tag
    return value


def _represent_verbatim(representer: RoundTripRepresenter, data: _Verbatim) -> Any:
    # Written under the tag its text implies, so the emitter keeps it plain instead of quoting it.
    return representer.represent_scalar(data.tag, str(data))


RoundTripRepresenter.add_representer(_Verbatim, _represent_verbatim)


class _EditConstructor(RoundTripConstructor):
    """Round-trip constructor that keeps a value PyYAML-style typing would reject as written.

    `due: 2026-13-01` (2.9, 2.10) is an invalid value, not malformed frontmatter, so the note must
    stay editable: the text is kept as a plain scalar and is written back unchanged.
    """

    def construct_yaml_timestamp(self, node: Any, values: Any = None) -> Any:
        try:
            return super().construct_yaml_timestamp(node, values)
        except ValueError:
            return _verbatim(node)

    def construct_yaml_int(self, node: Any) -> Any:
        try:
            return super().construct_yaml_int(node)
        except ValueError:
            return _verbatim(node)


_EditConstructor.add_constructor(
    "tag:yaml.org,2002:timestamp", _EditConstructor.construct_yaml_timestamp
)
_EditConstructor.add_constructor("tag:yaml.org,2002:int", _EditConstructor.construct_yaml_int)


def _yaml() -> YAML:
    yaml = YAML(typ="rt", pure=True)
    yaml.Constructor = _EditConstructor
    yaml.preserve_quotes = True
    yaml.width = 10**6  # never re-wrap a long value
    yaml.indent(mapping=2, sequence=4, offset=2)  # Obsidian's list layout: `  - item`
    return yaml


def _short(value: Any) -> str:
    """`value` for an error message: the text is cut at 64 characters."""
    return repr(value[:64] if isinstance(value, str) else value)[:80]


def _has_line_break(text: str) -> bool:
    """A control character other than tab, or a Unicode line or paragraph separator."""
    return any(unicodedata.category(c) in _LINE_BREAK_CATEGORIES and c != "\t" for c in text)


def _is_blank(line: str) -> bool:
    return not line.strip(" \t\r")


def _detect_eol(text: str) -> str:
    """2.4 rule 7: the line ending of the file's first line break; LF when it has none."""
    first = text.find("\n")
    return "\r\n" if first > 0 and text[first - 1] == "\r" else "\n"


def _frontmatter_head(text: str) -> str:
    """The raw frontmatter block (both fence lines and their line endings), or ''."""
    yaml_text, body, error = split_frontmatter(text)
    if yaml_text is None or error is not None:
        return ""
    return text[: len(text) - len(body)]


def _replace_frontmatter(text: str, changes: dict[str, Any]) -> str:
    """`text` with `changes` set in its frontmatter; the body bytes are untouched."""
    head = _frontmatter_head(text)
    if not head:
        raise ValidationError("the note has no frontmatter")
    opening_end = head.index("\n") + 1
    trailing = 1 if head.endswith("\n") else 0
    closing_start = head.rfind("\n", 0, len(head) - trailing) + 1
    yaml_raw = head[opening_end:closing_start]
    eol = _detect_eol(text)
    if len(yaml_raw.encode("utf-8")) > MAX_FRONTMATTER_BYTES:
        raise ValidationError(f"the frontmatter is larger than {MAX_FRONTMATTER_BYTES} bytes")
    try:
        data = _yaml().load(yaml_raw.replace("\r\n", "\n"))
        preamble = ""
        if data is None:  # an empty block (2.9): start a mapping, keep any comments
            data = CommentedMap()
            preamble = yaml_raw.replace("\r\n", "\n")
        for key, value in changes.items():
            data[key] = value
        out = io.StringIO()
        out.write(preamble)
        _yaml().dump(data, out)
    except Exception as exc:  # noqa: BLE001 - ruamel raises many types; all mean "cannot edit safely"
        raise ValidationError(
            f"the frontmatter cannot be edited safely: {type(exc).__name__}"
        ) from exc
    dumped = out.getvalue()
    if len(dumped.encode("utf-8")) > MAX_FRONTMATTER_BYTES:
        raise ValidationError(f"the frontmatter would exceed {MAX_FRONTMATTER_BYTES} bytes")
    if eol != "\n":
        dumped = dumped.replace("\n", eol)
    return head[:opening_end] + dumped + head[closing_start:] + text[len(head) :]


def _normalise_heading(level: str, text: str) -> tuple[int, str]:
    """(level, folded text) of an ATX heading's parts, as 2.4 rule 2 compares them."""
    return len(level), text.strip().rstrip("#").strip().casefold()


def _parse_heading(heading: str) -> tuple[int, str, str]:
    """(level, folded text, display text) of a target like `## Today`."""
    match = _HEADING_RE.fullmatch(heading.strip()) if isinstance(heading, str) else None
    if match is None:
        raise ValidationError(f"{_short(heading)} is not a heading such as '## Today'")
    level, folded = _normalise_heading(*match.groups())
    if not folded:
        raise ValidationError("the heading text is empty")
    display = match.group(2).strip().rstrip("#").strip()
    if len(display) > MAX_HEADING_LENGTH:
        raise ValidationError(f"the heading text is longer than {MAX_HEADING_LENGTH} characters")
    if any(unicodedata.category(char) in _YAML_ESCAPED_CATEGORIES for char in display):
        raise ValidationError("the heading text holds a control or line-separator character")
    return level, folded, display


def _heading_positions(lines: list[str]) -> list[tuple[int, int, str]]:
    """(index, level, folded text) of every ATX heading outside fenced code (2.4 rule 1)."""
    masked = mask_code("\n".join(lines)).split("\n")
    found = []
    for index, line in enumerate(lines):
        if not _is_blank(line) and not masked[index].strip():
            continue  # a fenced line
        match = _HEADING_RE.fullmatch(line.rstrip("\r"))
        if match is not None:
            level, folded = _normalise_heading(*match.groups())
            found.append((index, level, folded))
    return found


def _insert_under_heading(text: str, heading: str, new_lines: Sequence[str]) -> tuple[str, bool]:
    """Insert `new_lines` (no line endings) under `heading` by the rules of 2.4.

    Returns the new text and whether the heading was created (rule 6).
    """
    level, folded, display = _parse_heading(heading)
    head = _frontmatter_head(text)
    body = text[len(head) :]
    eol = _detect_eol(text)
    if head and not head.endswith("\n"):  # a file that ends at the closing fence (rule 8)
        head += eol
    cr = "\r" if eol == "\r\n" else ""
    blank = cr
    fresh = [line + cr for line in new_lines]
    lines = body.split("\n")
    headings = _heading_positions(lines)
    target = next((h for h in headings if h[1] == level and h[2] == folded), None)  # rule 3
    created = target is None
    if target is None:
        end = len(lines)
        position = None
    else:
        position = target[0]
        end = next((h[0] for h in headings if h[0] > position and h[1] <= level), len(lines))

    if end == len(lines):  # rule 8: the insertion point is the end of the file
        while lines and _is_blank(lines[-1]):
            lines.pop()
        if created:
            if head or lines:
                lines.append(blank)
            lines.append("#" * level + " " + display + cr)
            lines.append(blank)
        elif position is not None and len(lines) == position + 1:  # empty section
            lines.append(blank)
        if lines and cr and not lines[-1].endswith("\r"):
            lines[-1] += "\r"
        lines.extend(fresh)
        return head + "\n".join(lines) + "\n", created

    assert position is not None
    last = next((i for i in range(end - 1, position, -1) if not _is_blank(lines[i])), None)
    # An empty section receives the text after one blank line below the heading.
    before = [*lines[: position + 1], blank] if last is None else lines[: last + 1]
    return head + "\n".join([*before, *fresh, blank, *lines[end:]]), False


def _prepare_lines(text: str, marker: str) -> list[str]:
    """Plain text to lines with `marker` in front of each non-blank one.

    With a marker, a list marker the line already starts with is replaced, not doubled. With
    no marker the lines are written verbatim, so a line that would act as a heading, a front-matter
    fence or a code fence is refused.
    """
    if not isinstance(text, str):
        raise ValidationError("the text must be a string")
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError:
        raise ValidationError("text is not valid Unicode (lone surrogate)") from None
    if len(encoded) > MAX_BODY_BYTES:
        raise ValidationError(f"text is limited to {MAX_BODY_BYTES} bytes")
    if "\x00" in text:
        raise ValidationError("text holds a NUL character")
    lines = [line for line in _normalise_newlines(text).split("\n") if line.strip()]
    if not lines:
        raise ValidationError("the text is empty")
    if marker:
        return [marker + _LEADING_MARKER_RE.sub("", line, count=1) for line in lines]
    for line in lines:
        stripped = line.strip()
        if stripped in ("---", "...") or _STRUCTURAL_LINE_RE.match(line):
            raise ValidationError(f"{_short(line)} would act as a heading or fence, not as text")
    return lines


def is_untouched(text: str, template_text: str, note_date: date) -> bool:
    """True when a daily note still equals the daily template rendered for `note_date` (2.2).

    The note's frontmatter must parse with `type: daily`; only the bodies are compared, with all
    whitespace removed. The template is the vault's current one, so a customised template works.
    """
    parsed = parse_note(f"{note_date.isoformat()}.md", text.encode("utf-8"))
    if parsed.parse_error is not None or parsed.type != "daily":
        return False
    rendered = render(
        template_text, title=note_date.isoformat(), when=datetime.combine(note_date, time())
    )
    _, template_body, error = split_frontmatter(rendered)
    if error is not None:
        raise TemplateError(f"the daily template has malformed frontmatter: {error}")
    return "".join(parsed.body.split()) == "".join(template_body.split())


class VaultWriter:
    """Creates notes in the vault at `root`. `clock` returns the operation's datetime."""

    def __init__(self, root: str | os.PathLike[str], clock: Callable[[], datetime] = default_clock):
        self.root = Path(root).resolve()
        self._clock = clock

    # --- Public API ---------------------------------------------------------------------------

    def create(
        self,
        type: str,  # noqa: A002 - the API's field name
        title: str | None = None,
        *,
        project: str | None = None,
        priority: str | None = None,
        due: str | date | None = None,
        status: str | None = None,
        body: str | None = None,
    ) -> CreatedNote:
        """Create one note from the vault's template for `type`.

        `title` is the human title (the file name stem after sanitising); a daily note's title
        is its date and defaults to today; a capture without a title is named from its text.
        """
        spec = NoteSpec(type, title, project, priority, due, status, body)
        return self.create_many([spec])[0]

    def create_many(self, specs: Sequence[NoteSpec]) -> list[CreatedNote]:
        """Create several notes as one operation: one clock read, ids one second apart (C20).

        At most 50 notes. Every note is validated before the first is written. A failure while
        writing leaves the notes already written in place (nothing is deleted by the app).
        """
        if len(specs) > MAX_NOTES_PER_OPERATION:
            raise ValidationError(f"at most {MAX_NOTES_PER_OPERATION} notes per operation")
        for spec in specs:
            for field in (spec.title, spec.body, spec.project, spec.status, spec.priority):
                if isinstance(field, str):
                    try:
                        field.encode("utf-8")  # strict: a lone surrogate is not UTF-8
                    except UnicodeEncodeError:
                        raise ValidationError(
                            "text is not valid Unicode (lone surrogate)"
                        ) from None
            if spec.body is not None and len(spec.body.encode("utf-8")) > MAX_BODY_BYTES:
                raise ValidationError(f"a body is limited to {MAX_BODY_BYTES} bytes")
        try:
            operation = _Operation(self.root, self._clock())
            prepared = [self._prepare(spec, index, operation) for index, spec in enumerate(specs)]
        except OSError as exc:
            logger.exception("reading the vault failed")
            raise WriterError(f"could not read the vault: {_describe(exc)}") from exc
        created = []
        for rel, text, note in prepared:
            written = self._write_new(rel, text)
            created.append(CreatedNote(written, note.note_id, note.title, note.type))
        return created

    def _write_new(self, rel: str, text: str) -> str:
        """Atomically create the confined file `rel` (never overwrites); returns its path.

        Temp file `.<stem>.sbw-tmp-<8 hex>` in the target directory, fsync, then published with
        `os.link` + `os.unlink` (see the module docstring). Only a temp file this call created is
        removed on failure. LF line endings, UTF-8, no BOM.
        """
        try:
            parts = self._validate_relative(rel)  # reads .sbignore
            return self._publish(parts, _normalise_newlines(text).encode("utf-8"))
        except OSError as exc:
            logger.exception("writing %s failed", rel)
            raise WriterError(f"could not write {rel}: {_describe(exc)}") from exc

    @staticmethod
    def _write_temp(directory: Path, stem: str, data: bytes, mode: int | None = None) -> Path:
        """Write `data` to `.<stem>.sbw-tmp-<8 hex>` in `directory` and fsync it (2.9).

        The temp is created exclusively and never through a symlink; `mode` (if given) is set on
        it. It is removed again if writing fails; on success the caller owns it.
        """
        temp = directory / f".{stem}.sbw-tmp-{secrets.token_hex(4)}"
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o666)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                if mode is not None:
                    os.fchmod(handle.fileno(), mode)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
        return temp

    def _publish(self, parts: list[str], data: bytes) -> str:
        directory = self._directory(parts[:-1], create=True)
        assert directory is not None
        name = parts[-1]
        final = directory / name
        self._refuse_existing(directory, name)  # the clean 409; the link below is the guarantee
        temp = self._write_temp(directory, name[: -len(".md")], data)
        temp_created = True
        try:
            try:
                os.link(temp, final)
            except FileExistsError:
                raise ConflictError(f"{name!r} already exists in {directory.name!r}") from None
            except OSError as exc:
                if exc.errno not in _LINK_FALLBACK_ERRNOS:
                    raise
                logger.warning("hard links are not available here (%s); using os.replace", exc)
                self._refuse_existing(directory, name)
                os.replace(temp, final)
                temp_created = False
            else:
                os.unlink(temp)
                temp_created = False
        except BaseException:
            if temp_created:
                temp.unlink(missing_ok=True)
            raise
        _fsync_directory(directory)
        written = final.relative_to(self.root).as_posix()
        logger.info("created note %s", written)
        return written

    # --- Editing an existing note -------------------------------------------------------------

    def set_frontmatter(
        self, rel_path: str, changes: dict[str, Any], *, expected_hash: str
    ) -> EditResult:
        """Set frontmatter keys; unknown keys, key order, comments and quoting are preserved.

        New keys go at the end. A value is a string, number, bool, date, None or a list of those;
        an ISO date string under `created`/`due`/`decided` is written as an unquoted YAML date.
        """
        clean = self._clean_changes(changes)
        return self._edit(
            rel_path, expected_hash, lambda text, _note: (_replace_frontmatter(text, clean), False)
        )

    def set_status(
        self, rel_path: str, status: str, *, expected_hash: str, evidence: str | None = None
    ) -> EditResult:
        """Set `status` after checking the note type's vocabulary (2.3), in one write.

        When the status is `done` and `evidence` is not blank, it is appended under `## Notes`
        (each line as a `- ` bullet; the heading is added if missing). Non-blank `evidence` with
        any other status is a `ValidationError`; nothing is written.
        """

        if not isinstance(status, str):
            raise ValidationError("the status must be a string")
        if evidence is not None:
            if not isinstance(evidence, str):
                raise ValidationError("the evidence must be a string")
            if evidence.strip() and status != "done":
                raise ValidationError("evidence can only be given with the status 'done'")

        def transform(text: str, note) -> tuple[str, bool]:
            allowed = conventions.STATUSES.get(note.type)
            if not allowed:
                raise ValidationError(f"a {note.type} note has no status")
            if status not in allowed:
                raise ValidationError(f"status {_short(status)} is not allowed for {note.type}")
            text = _replace_frontmatter(text, {"status": status})
            if evidence is not None and evidence.strip():
                text, created = _insert_under_heading(
                    text, "## Notes", _prepare_lines(evidence, "- ")
                )
                return text, created
            return text, False

        return self._edit(rel_path, expected_hash, transform)

    def append_to_section(
        self,
        rel_path: str,
        heading: str,
        text: str,
        *,
        expected_hash: str,
        marker: str | None = None,
    ) -> EditResult:
        """Append plain `text` under `heading` (for example `## Today`) by the rules of 2.4.

        The writer adds the list marker to every non-blank line: `- [ ] ` under Today and
        Follow-ups of a daily note, `- ` everywhere else. `marker` overrides it; only `""` (lines
        verbatim), `"- "` and `"- [ ] "` are allowed.
        `section_created` is set when the heading had to be added.
        """
        _, folded, _ = _parse_heading(heading)
        if marker is not None and marker not in _ALLOWED_MARKERS:
            raise ValidationError("the marker must be '', '- ' or '- [ ] '")

        def transform(content: str, note) -> tuple[str, bool]:
            chosen = marker
            if chosen is None:
                checkbox = note.type == "daily" and folded in _CHECKBOX_SECTIONS
                chosen = "- [ ] " if checkbox else "- "
            return _insert_under_heading(content, heading, _prepare_lines(text, chosen))

        return self._edit(rel_path, expected_hash, transform)

    def fill_untouched(
        self, rel_path: str, items: Mapping[str, Sequence[str]], *, expected_hash: str
    ) -> EditResult:
        """Insert carry-forward `items` into a daily note that is still untouched (2.2).

        `items` maps a standup heading (`"Today"`, ...; see `conventions.STANDUP_HEADINGS`) to
        complete lines, written verbatim (markers and indentation included). The note is compared
        with the vault's current daily template rendered for its date; if it differs it is touched
        and returned unchanged (`changed=False`, nothing written). A heading the note lacks is
        added (2.4 rule 6), in template order. The fill is one atomic write.
        """
        known = {name.casefold(): name for name in conventions.STANDUP_HEADINGS}
        wanted: list[tuple[str, list[str]]] = []
        for name, lines in items.items():
            if not isinstance(name, str) or name.casefold() not in known:
                raise ValidationError(f"{_short(name)} is not a standup heading")
            if isinstance(lines, str) or any(
                not isinstance(line, str) or not line.strip() or "\n" in line or "\r" in line
                for line in lines
            ):
                raise ValidationError(
                    f"the items for {_short(name)} must be single non-blank lines"
                )
            if lines:
                for line in lines:
                    _prepare_lines(line, "")  # size, NUL, surrogate and structure checks
                wanted.append((known[name.casefold()], list(lines)))
        # Headings the note lacks are added in template order, whatever order `items` came in.
        wanted.sort(key=lambda entry: conventions.STANDUP_HEADINGS.index(entry[0]))

        def transform(text: str, note) -> tuple[str, bool]:
            stem = Path(rel_path).stem
            try:
                if not _ISO_DATE_RE.fullmatch(stem):
                    raise ValueError(stem)
                note_date = date.fromisoformat(stem)
            except ValueError:
                raise ValidationError(
                    f"{_short(rel_path)} is not a daily note (YYYY-MM-DD)"
                ) from None
            if not is_untouched(text, load_template(self.root, "daily"), note_date):
                raise _Touched
            created = False
            for name, lines in wanted:
                text, added = _insert_under_heading(text, f"## {name}", lines)
                created = created or added
            return text, created

        return self._edit(rel_path, expected_hash, transform)

    @staticmethod
    def _clean_changes(changes: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(changes, dict) or not changes:
            raise ValidationError("changes must be a non-empty mapping")
        clean: dict[str, Any] = {}
        for key, value in changes.items():
            VaultWriter._check_key(key)
            if isinstance(value, list | tuple) and len(value) > MAX_FRONTMATTER_LIST_ITEMS:
                raise ValidationError(
                    f"the value of {_short(key)} has more than {MAX_FRONTMATTER_LIST_ITEMS} items"
                )
            for item in value if isinstance(value, list | tuple) else [value]:
                VaultWriter._check_value(key, item)
            if key in conventions.DATE_KEYS and isinstance(value, str):
                value = date.fromisoformat(VaultWriter._due(value, key))
            clean[key] = list(value) if isinstance(value, tuple) else value
        return clean

    @staticmethod
    def _check_key(key: Any) -> None:
        if (
            not isinstance(key, str)
            or len(key) > MAX_FRONTMATTER_KEY_LENGTH
            or key != key.strip()
            or not _FRONTMATTER_KEY_RE.fullmatch(key)
        ):
            raise ValidationError(f"{_short(key)} is not a usable frontmatter key")
        if key in _IDENTITY_KEYS:
            raise ValidationError(f"{key!r} identifies the note and is not changed here")

    @staticmethod
    def _check_value(key: str, item: Any) -> None:
        if not isinstance(item, _FRONTMATTER_VALUE_TYPES) or isinstance(item, datetime):
            raise ValidationError(f"the value of {_short(key)} is not a plain YAML value")
        if isinstance(item, str):
            try:
                encoded = item.encode("utf-8")
            except UnicodeEncodeError:
                raise ValidationError("text is not valid Unicode (lone surrogate)") from None
            if len(encoded) > MAX_FRONTMATTER_STRING_BYTES:
                raise ValidationError(
                    f"the value of {_short(key)} is over {MAX_FRONTMATTER_STRING_BYTES} bytes"
                )
            if _has_line_break(item):
                raise ValidationError(
                    f"the value of {_short(key)} holds a control or line-separator character"
                )
        if isinstance(item, float) and not math.isfinite(item):
            raise ValidationError(f"the value of {_short(key)} is not a finite number")

    def _edit(
        self,
        rel_path: str,
        expected_hash: str,
        transform: Callable[[str, Any], tuple[str, bool]],
    ) -> EditResult:
        """Read, check the hash, transform the text and publish the result atomically."""
        if not isinstance(expected_hash, str):
            raise ValidationError("expected_hash must be a string")
        expected = expected_hash.strip().lower()
        try:
            target = self._locate(rel_path)
            written = target.relative_to(self.root).as_posix()
            data = self._read_bytes(target)
            if content_hash(data) != expected:
                raise ConflictError(f"{_short(rel_path)} changed since it was read")
            note = parse_note(rel_path, data)
            if note.parse_error is not None:
                raise ValidationError(
                    f"{_short(rel_path)} has malformed content: {note.parse_error}"
                )
            bom = _BOM if data.startswith(_BOM) else b""
            text = data[len(bom) :].decode("utf-8")
            try:
                new_text, section_created = transform(text, note)
            except _Touched:  # a touched daily note is returned as it is
                return EditResult(written, expected, changed=False)
            new_data = bom + new_text.encode("utf-8")
            if new_data == data:  # nothing to change: publish nothing
                return EditResult(written, expected, changed=False)
            self._check_result(rel_path, note, new_data)
            self._replace(target, new_data, expected)
        except OSError as exc:
            logger.exception("editing %s failed", _short(rel_path))
            raise WriterError(f"could not edit {_short(rel_path)}: {_describe(exc)}") from exc
        logger.info("edited note %s", written)
        return EditResult(written, content_hash(new_data), section_created)

    @staticmethod
    def _check_result(rel_path: str, before, new_data: bytes) -> None:
        """A safety net: the edited file must still parse and keep every key it was not given."""
        after = parse_note(rel_path, new_data)
        if after.parse_error is not None:
            raise ValidationError("the edit would leave the note malformed; nothing was written")
        missing = set(before.frontmatter) - set(after.frontmatter)
        if missing:
            raise ValidationError("the edit would drop frontmatter keys; nothing was written")

    def _locate(self, rel: str) -> Path:
        """The existing regular file for `rel` (letter case matched on disk), confined."""
        parts = self._validate_relative(rel)
        directory = self._directory(parts[:-1], create=False)
        entry = find_child_ci(directory, parts[-1]) if directory is not None else None
        if entry is None:
            raise PathError(f"{_short(rel)} does not exist")
        if entry.is_symlink() or not entry.is_file():
            raise PathError(f"{_short(rel)} is not a regular file")
        return entry

    @staticmethod
    def _read_bytes(path: Path) -> bytes:
        """Read a file without following a symlink at the last component; refuse over 5 MiB."""
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as handle:
            if os.fstat(handle.fileno()).st_size > MAX_NOTE_BYTES:
                raise ValidationError(f"a note over {MAX_NOTE_BYTES} bytes is not edited")
            return handle.read(MAX_NOTE_BYTES + 1)

    def _replace(self, target: Path, data: bytes, expected: str) -> None:
        """Write a temp file, re-hash the target, then `os.replace`; temp removed on failure."""
        directory = target.parent
        temp = None
        try:
            mode = stat.S_IMODE(os.stat(target).st_mode)  # the replacement keeps the note's mode
            temp = self._write_temp(directory, target.name[: -len(".md")], data, mode)
            if content_hash(self._read_bytes(target)) != expected:  # an editor wrote it meanwhile
                raise ConflictError(f"{target.name!r} changed while it was being written")
            os.replace(temp, target)
            temp = None
        except FileNotFoundError:
            raise ConflictError(f"{target.name!r} was removed while it was being written") from None
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
        _fsync_directory(directory)

    # --- Confinement --------------------------------------------------------------------------

    def _validate_relative(self, rel: str) -> list[str]:
        """Checks that need no disk: shape, characters, length, `.md`, ignore rules."""
        if not isinstance(rel, str) or not rel:
            raise PathError("the path is empty")
        if "\\" in rel or rel.startswith("/") or _DRIVE_RE.match(rel):
            raise PathError(f"{rel!r} is not a vault-relative path")
        if utf16_length(rel) > MAX_PATH_LENGTH:
            raise PathError(f"the path is longer than {MAX_PATH_LENGTH} characters")
        parts = rel.split("/")
        if any(part in ("", ".", "..") for part in parts):
            raise PathError(f"{rel!r} has an empty or dot segment")
        unsafe = conventions.CONTROL_CHARACTERS | conventions.WINDOWS_ILLEGAL_CHARACTERS
        if any(char in unsafe for char in rel.replace("/", "")):
            raise PathError(f"{rel!r} holds a character a file name cannot have")
        if any(is_reserved_name(part) for part in parts):
            raise PathError(f"{rel!r} has a segment that is a reserved device name")
        if not rel.casefold().endswith(".md") or len(parts[-1]) == len(".md"):
            raise PathError(f"{rel!r} is not a .md file")
        if is_ignored(rel, read_sbignore(self.root)):
            raise PathError(f"{rel!r} is an ignored path")
        return parts

    def _directory(self, parts: list[str], *, create: bool) -> Path | None:
        """The directory for `parts` below the root, matched case-insensitively on disk.

        Refuses a symlink or a file on the way. A missing folder is created only when
        `create` is set and the folder is a Phase 1 folder or a year folder (2.5); with
        `create` unset, None means it does not exist yet.
        """
        current = self.root
        missing_from = len(parts)
        for position, part in enumerate(parts):
            entry = find_child_ci(current, part)
            if entry is None:
                missing_from = position
                break
            if entry.is_symlink():
                raise PathError(f"{entry.name!r} is a symlink")
            if not entry.is_dir():
                raise PathError(f"{entry.name!r} is not a folder")
            current = entry
        if missing_from < len(parts):
            if not create:
                return None
            for depth in range(missing_from, len(parts)):  # check all before creating any
                folder = "/".join(parts[: depth + 1])
                if not self._may_create(folder):
                    raise PathError(f"folder {folder!r} does not exist and is not created")
            for part in parts[missing_from:]:
                current = current / part
                try:
                    os.mkdir(current)
                except FileExistsError:  # another writer created it first: accept a real folder
                    if current.is_symlink() or not current.is_dir():
                        raise PathError(f"{part!r} is not a folder") from None
        resolved = Path(os.path.realpath(current))
        if resolved != self.root and self.root not in resolved.parents:
            raise PathError("the folder resolves outside the vault")
        return current

    @staticmethod
    def _may_create(folder: str) -> bool:
        """A Phase 1 folder (or a parent of one), or a year folder below the daily folder."""
        folded = folder.casefold()
        if any(
            known.casefold() == folded or known.casefold().startswith(folded + "/")
            for known in conventions.PHASE_1_FOLDERS
        ):
            return True
        parent, _, leaf = folded.rpartition("/")
        return parent == conventions.TYPE_FOLDERS["daily"].casefold() and bool(
            _YEAR_FOLDER_RE.fullmatch(leaf)
        )

    @staticmethod
    def _refuse_existing(directory: Path, name: str) -> None:
        if _exists_ci(directory, name):
            raise ConflictError(f"{name!r} already exists in {directory.name!r}")

    # --- Building a note ----------------------------------------------------------------------

    def _prepare(
        self, spec: NoteSpec, index: int, operation: _Operation
    ) -> tuple[str, str, CreatedNote]:
        note_type = spec.type
        if note_type not in conventions.KNOWN_TYPES:
            raise ValidationError(f"type {note_type!r} cannot be created")
        at = operation.at(index)
        folder, candidates = self._names(spec, at)
        stem = self._free_stem(folder, candidates, operation)
        rel = f"{folder}/{stem}.md"
        if utf16_length(rel) > MAX_PATH_LENGTH:
            raise PathError(f"the path is longer than {MAX_PATH_LENGTH} characters")
        if note_type == "project":
            self._refuse_duplicate_project(stem, operation)
        text = render(load_template(self.root, note_type), title=stem, when=at)
        text = self._apply_fields(text, spec, operation, rel)
        if spec.body:
            text = text.rstrip("\n") + "\n\n" + _normalise_newlines(spec.body).strip("\n") + "\n"
        parsed = parse_note(rel, text.encode("utf-8"))
        if parsed.parse_error is not None or parsed.type != note_type:
            raise TemplateError(
                f"the {note_type} template does not produce a valid {note_type} note: "
                f"{parsed.parse_error or 'type is ' + repr(parsed.type)}"
            )
        operation.planned.append(rel)
        return rel, text, CreatedNote(rel, at.strftime("%Y%m%d%H%M%S"), stem, note_type)

    def _names(self, spec: NoteSpec, at: datetime) -> tuple[str, list[str]]:
        """The folder and the stems to try in order (a capture named from its text gets two)."""
        folder = conventions.TYPE_FOLDERS[spec.type]
        if spec.type == "daily":
            stem = (spec.title or at.date().isoformat()).strip()
            if not _ISO_DATE_RE.fullmatch(stem):
                raise SanitizeError(f"a daily note's title is a YYYY-MM-DD date, not {stem!r}")
            try:
                date.fromisoformat(stem)
            except ValueError:
                raise SanitizeError(f"{stem!r} is not a calendar date") from None
            return f"{folder}/{stem[:4]}", [stem]
        if spec.type == "capture" and not (spec.title or "").strip():
            words = " ".join((spec.body or "").split()[:CAPTURE_WORDS])
            return folder, [
                sanitize_stem(f"{at:%Y-%m-%d} {at:{clock_format}} {words}", fallback="Untitled")
                for clock_format in ("%H%M", "%H%M%S")  # second try: seconds appended (C22)
            ]
        fallback = f"Untitled {at:%Y-%m-%d %H%M%S}"  # rule 8
        return folder, [sanitize_stem(spec.title or "", fallback=fallback)]

    def _free_stem(self, folder: str, candidates: list[str], operation: _Operation) -> str:
        for stem in candidates:
            if not self._taken(folder, stem, operation):
                return stem
        raise ConflictError(f"{candidates[-1]!r} already exists in {folder!r}")

    def _taken(self, folder: str, stem: str, operation: _Operation) -> bool:
        rel = f"{folder}/{stem}.md".casefold()
        if any(planned.casefold() == rel for planned in operation.planned):
            return True
        directory = self._directory(folder.split("/"), create=False)
        return directory is not None and _exists_ci(directory, f"{stem}.md")

    def _refuse_duplicate_project(self, stem: str, operation: _Operation) -> None:
        """A project whose slug matches an existing project note is rejected (2.1)."""
        slug = project_note_slug(stem)
        if any(project_note_slug(path) == slug for path in self._project_paths(operation)):
            raise ConflictError(f"a project note with the slug {slug!r} already exists")

    def _apply_fields(self, text: str, spec: NoteSpec, operation: _Operation, rel: str) -> str:
        note_type = spec.type
        if spec.status is not None:
            allowed = conventions.STATUSES.get(note_type)
            if not allowed or spec.status not in allowed:
                raise ValidationError(f"status {spec.status!r} is not allowed for {note_type}")
            text = _set_frontmatter(text, "status", spec.status, note_type)
        if spec.priority is not None:
            if spec.priority not in conventions.PRIORITIES:
                raise ValidationError(f"priority {spec.priority!r} is not one of low, medium, high")
            text = _set_frontmatter(text, "priority", spec.priority, note_type)
        if spec.due is not None:
            text = _set_frontmatter(text, "due", self._due(spec.due), note_type)
        if spec.project is not None:
            link = self._project_link(spec.project, operation, rel)
            text = _set_frontmatter(text, "project", _yaml_double_quoted(link), note_type)
        return text

    @staticmethod
    def _due(value: str | date, field: str = "due") -> str:
        raw = value.isoformat() if isinstance(value, date) else str(value).strip()
        try:
            if not _ISO_DATE_RE.fullmatch(raw):
                raise ValueError(raw)
            return date.fromisoformat(raw).isoformat()
        except ValueError:
            raise ValidationError(f"{field} {_short(raw)} is not a YYYY-MM-DD date") from None

    def _project_paths(self, operation: _Operation) -> list[str]:
        prefix = conventions.TYPE_FOLDERS["project"].casefold() + "/"
        return [p for p in operation.note_paths() if p.casefold().startswith(prefix)]

    def _project_link(self, value: str, operation: _Operation, new_rel: str) -> str:
        """`[[Stem]]`, or `[[02-Work/Projects/Stem]]` when the stem is not unique on disk (2.5)."""
        slug = project_slug(value)
        resolution = resolve_project(slug, self._project_paths(operation)) if slug else None
        if resolution is None or resolution.status == "unknown":
            raise ValidationError(f"no project note matches {value!r}")
        if resolution.status == "duplicate":
            raise ValidationError(f"several project notes match {value!r}")
        assert resolution.path is not None
        target = resolution.path.removesuffix(".md")
        stem = target.rpartition("/")[2].casefold()
        # The note being created counts too: a note named like its project needs the qualified link.
        paths = [*operation.note_paths(), new_rel]
        same_stem = [p for p in paths if Path(p).stem.casefold() == stem]
        return f"[[{Path(target).name if len(same_stem) == 1 else target}]]"
