"""The vault writer: the only code that creates files in the vault (plan sections 2.5, 2.9, 2.12).

P1-22 covers confinement, sanitising and atomic create from a template. The writer never
touches the database; the indexer picks files up (or `index_single_file` is called by the API).

Every target is resolved under the vault root: no `..`, no absolute path, no symlinked
component, no ignored path, only `.md`. Existence, uniqueness and emitted links are read from the
filesystem, never from the index.

Publishing never overwrites: the finished temp file is hard-linked to its final name (`os.link`
fails with EEXIST if the name is taken, in any letter case on the vault's drive) and the temp is
then unlinked. Where the filesystem refuses links (EPERM, ENOTSUP, EXDEV) it falls back to
`os.replace` after a last existence check, with a logged warning.

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
import logging
import os
import re
import secrets
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

from django.utils import timezone

from vault import clock as vault_clock
from vault import conventions
from vault.ignore import is_ignored, iter_note_paths, read_sbignore
from vault.parser import parse_note
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
    "NoteSpec",
    "PathError",
    "SanitizeError",
    "TemplateError",
    "ValidationError",
    "VaultWriter",
    "WriterError",
    "default_clock",
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


class PathError(WriterError):
    """A target escapes the vault, is ignored, is not a `.md` file, or sits in a folder the
    writer may not create (API: 400)."""


class ConflictError(WriterError):
    """A note with the same name (case-insensitive) exists in the folder (API: 409)."""


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

    def _publish(self, parts: list[str], data: bytes) -> str:
        directory = self._directory(parts[:-1], create=True)
        assert directory is not None
        name = parts[-1]
        final = directory / name
        self._refuse_existing(directory, name)  # the clean 409; the link below is the guarantee
        temp = directory / f".{name[: -len('.md')]}.sbw-tmp-{secrets.token_hex(4)}"
        temp_created = False
        try:
            descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o666)
            temp_created = True
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
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
    def _due(value: str | date) -> str:
        raw = value.isoformat() if isinstance(value, date) else str(value).strip()
        try:
            if not _ISO_DATE_RE.fullmatch(raw):
                raise ValueError(raw)
            return date.fromisoformat(raw).isoformat()
        except ValueError:
            raise ValidationError(f"due {raw!r} is not a YYYY-MM-DD date") from None

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
