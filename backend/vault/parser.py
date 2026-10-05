"""Parse one vault file into the indexed fields of a note (plan sections 2.9 and 2.10).

`parse_note` takes a file's bytes and vault-relative path and returns a
`ParsedNote`. It never raises on any input: whatever cannot be read is recorded
in `parse_error` or in the invalid-value details, and the note is still returned.
Questions that need other notes (duplicate ids, link and project resolution) are
answered by `vault.links` and `vault.slug`.
"""

import math
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import TaggedScalar
from ruamel.yaml.constructor import RoundTripConstructor

from vault import conventions
from vault.links import MASK_PLACEHOLDER, WIKILINK_RE, link_targets, mask_code, note_stem
from vault.slug import project_slug

# More values than any real frontmatter holds. Reached only by alias expansion
# (`&a [*a, *a, ...]` nested), which would otherwise take unbounded time and memory.
MAX_FRONTMATTER_VALUES = 10_000

_OPENING_LINE = "---"
_CLOSING_LINES = ("---", "...")
_ISO_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_TAG_START_RE = re.compile(r"(?:^|(?<=\s))#", re.MULTILINE)
# Characters PostgreSQL cannot store: NUL and unpaired surrogates (2.10). A YAML
# escape such as "\0" or "\ud800" produces them from clean bytes.
_UNSTORABLE_RE = re.compile("[\x00\ud800-\udfff]")
_STR_TAG = "tag:yaml.org,2002:str"


@dataclass(frozen=True, slots=True)
class ParsedNote:
    """Everything the index stores for one note that can be read from its own file."""

    path: str
    title: str
    type: str
    status: str | None
    priority: str | None
    project: str | None  # the slug (2.1)
    due: date | None
    created: date | None
    note_id: str | None
    frontmatter: dict[str, Any]  # JSON-safe plain values, keys in file order (2.10)
    body: str
    links: frozenset[str]  # the 2.8 link set
    tags: frozenset[str]  # the 2.10 tag set
    parse_error: str | None  # set only for the malformed cases of 2.9
    # Details for the conformance checker (2.11), so it never re-parses:
    invalid_dates: tuple[str, ...]  # F7: keys of DATE_KEYS present, not null and invalid
    invalid_priority: bool  # F8: priority present, not null, non-scalar or outside PRIORITIES
    unknown_type: bool  # W4: `type` is a usable string, not `note`, outside KNOWN_TYPES
    dropped_tags: tuple[str, ...]  # W6: frontmatter `tags` items dropped as invalid
    unusable_status: bool  # F3: `status` present, not null, and a list or mapping
    unusable_project: bool  # W5: `project` present, not null, and yielding no slug


class _FrontmatterError(ValueError):
    """Frontmatter that loaded but cannot be used as plain data."""


class _YamlTimestamp(str):
    """A YAML date or timestamp: its text as written, plus the parsed value."""

    parsed: date


class _StorableConstructor(RoundTripConstructor):
    """Round-trip constructor whose scalars are storable as JSON (2.9, 2.10).

    Dates and timestamps load as their text as written, carrying the parsed value
    for the 2.10 date rule. `due: 2026-13-01` matches the timestamp pattern but
    makes the stock constructor raise a plain ValueError that aborts the whole
    load; under 2.9 that is an invalid value, not malformed frontmatter, so it
    loads as a plain string and the date rule marks it invalid. An integer the
    library cannot convert (several thousand digits) is kept as its text the same
    way. Non-finite floats (`.nan`, `.inf`, `1e400`) load as their YAML text.
    """

    def construct_yaml_int(self, node: Any) -> Any:
        try:
            return super().construct_yaml_int(node)
        except ValueError:
            return str(node.value)

    def construct_yaml_timestamp(self, node: Any, values: Any = None) -> Any:
        try:
            parsed = super().construct_yaml_timestamp(node, values)
        except ValueError:
            return str(node.value)
        timestamp = _YamlTimestamp(node.value)
        timestamp.parsed = parsed
        return timestamp

    def construct_yaml_float(self, node: Any) -> Any:
        value = super().construct_yaml_float(node)
        if not math.isfinite(value):
            return str(node.value)
        return value


_StorableConstructor.add_constructor(
    "tag:yaml.org,2002:timestamp", _StorableConstructor.construct_yaml_timestamp
)
_StorableConstructor.add_constructor(
    "tag:yaml.org,2002:float", _StorableConstructor.construct_yaml_float
)
_StorableConstructor.add_constructor(
    "tag:yaml.org,2002:int", _StorableConstructor.construct_yaml_int
)


def parse_note(path: str, data: bytes) -> ParsedNote:
    """Parse a file's bytes; `path` is vault-relative with `/` separators."""
    text, parse_error = _decode(data)
    loaded: Mapping[str, Any] = {}  # as loaded, for the date rule
    frontmatter: dict[str, Any] = {}  # the storable copy
    body = text
    if parse_error is None:
        yaml_text, body, parse_error = split_frontmatter(text)
        if yaml_text is not None and parse_error is None:
            loaded, frontmatter, parse_error = _load_frontmatter(yaml_text)
        if parse_error is not None:
            body = text  # 2.9: a malformed note's body is the whole file

    note_type, unknown_type = _read_type(frontmatter.get("type"))
    dates = {key: _read_date(loaded.get(key)) for key in conventions.DATE_KEYS}
    priority_value = frontmatter.get("priority")
    priority = _scalar_text(priority_value)
    project_value = frontmatter.get("project")
    project_text = _scalar_text(project_value)
    project = project_slug(project_text) if project_text is not None else None
    status_value = frontmatter.get("status")
    note_id = _scalar_text(frontmatter.get("id"))
    frontmatter_tags, dropped_tags = _frontmatter_tags(frontmatter.get("tags"))

    return ParsedNote(
        path=path,
        title=note_stem(path),
        type=note_type,
        status=_scalar_text(status_value),
        priority=priority,
        project=project,
        due=dates["due"][0],
        created=dates["created"][0],
        note_id=note_id if note_id and note_id.strip() else None,  # 2.10: empty id is no id
        frontmatter=frontmatter,
        body=body,
        links=frozenset(_frontmatter_links(frontmatter) | link_targets(body)),
        tags=frozenset(frontmatter_tags | _inline_tags(body)),
        parse_error=parse_error,
        invalid_dates=tuple(key for key, (_, invalid) in dates.items() if invalid),
        invalid_priority=priority_value is not None
        and (priority is None or priority not in conventions.PRIORITIES),
        unknown_type=unknown_type,
        dropped_tags=dropped_tags,
        unusable_status=isinstance(status_value, list | dict),
        unusable_project=project_value is not None and project is None,
    )


def split_frontmatter(text: str) -> tuple[str | None, str, str | None]:
    """Split text into (frontmatter YAML, body, error) following 2.9.

    Frontmatter starts with a first line that is exactly `---` and ends at the
    next line that is exactly `---` or `...`; a trailing CR is ignored. Without an
    opening line the YAML is None and the body is the whole text. An opening line
    with no closing line is an error.
    """
    first_end = text.find("\n")
    first_line = text if first_end == -1 else text[:first_end]
    if first_line.rstrip("\r") != _OPENING_LINE:
        return None, text, None
    if first_end == -1:
        return None, text, "unterminated frontmatter: no closing --- or ... line"

    start = position = first_end + 1
    while position <= len(text):
        line_end = text.find("\n", position)
        line = text[position:] if line_end == -1 else text[position:line_end]
        if line.rstrip("\r") in _CLOSING_LINES:
            body = "" if line_end == -1 else text[line_end + 1 :]
            return text[start:position].replace("\r\n", "\n"), body, None
        if line_end == -1:
            break
        position = line_end + 1
    return None, text, "unterminated frontmatter: no closing --- or ... line"


def _decode(data: bytes) -> tuple[str, str | None]:
    # 2.9 and 2.10: undecodable bytes and NUL characters are replaced with U+FFFD
    # (REPLACEMENT CHARACTER) and the file is malformed, so the problem shows on
    # the Index Status page and no NUL reaches the database.
    error = None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        text = data.decode("utf-8", errors="replace")
        error = f"invalid UTF-8 at byte {exc.start}"
    if "\x00" in text:
        error = error or f"NUL character at byte {data.find(b'\x00')}"
        text = text.replace("\x00", "\ufffd")
    return text.removeprefix("\ufeff"), error  # U+FEFF: byte order mark


def _load_frontmatter(yaml_text: str) -> tuple[Mapping[str, Any], dict[str, Any], str | None]:
    """Load frontmatter: (the mapping as loaded, its storable copy, error)."""
    yaml = YAML(typ="rt", pure=True)
    yaml.Constructor = _StorableConstructor
    try:
        loaded = yaml.load(yaml_text)
        if loaded is None:  # an empty block or only comments: valid, no keys (2.9)
            return {}, {}, None
        if not isinstance(loaded, Mapping):
            kind = "list" if isinstance(loaded, list | tuple) else "scalar"
            return {}, {}, f"frontmatter is a {kind}, not a mapping"
        return loaded, _to_plain(loaded, set(), [0]), None
    # Any failure to load is malformed frontmatter (2.9): syntax errors, duplicate
    # keys (DuplicateKeyError is a warning class), bad explicit tags, recursion
    # depth. The parser must never raise, so the error is recorded, not swallowed.
    except Exception as exc:  # noqa: BLE001
        summary = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
        return {}, {}, f"{type(exc).__name__}: {summary}".rstrip(": ")


def _to_plain(value: Any, ancestors: set[int], count: list[int]) -> Any:
    """Convert ruamel round-trip values to plain dict, list, str, int, float, bool, None."""
    count[0] += 1
    if count[0] > MAX_FRONTMATTER_VALUES:
        raise _FrontmatterError(f"more than {MAX_FRONTMATTER_VALUES} values")
    if isinstance(value, Mapping | list | tuple | set):
        if id(value) in ancestors:
            raise _FrontmatterError("an alias refers to a value that contains it")
        ancestors.add(id(value))
        if isinstance(value, Mapping):
            # Keys become text; non-string keys that collide with another key after
            # conversion keep the later value (see _key_text).
            plain: Any = {
                _key_text(key): _to_plain(item, ancestors, count) for key, item in value.items()
            }
        else:
            plain = [_to_plain(item, ancestors, count) for item in value]
        ancestors.discard(id(value))
        return plain
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):  # finite: the constructor turns the others into text
        return float(value)
    if isinstance(value, TaggedScalar):  # `!!str x` or an unknown tag such as `!foo bar`
        return _storable_text(value.value)
    return _storable_text(value)


def _key_text(key: Any) -> str:
    # Keys become strings so the mapping can be stored as JSON. Non-string keys
    # are rare in frontmatter; two keys with the same text keep the later value.
    return _storable_text(key)


def _storable_text(value: Any) -> str:
    """An exact `str`; NUL or an unpaired surrogate makes the frontmatter malformed."""
    text = str(value)
    found = _UNSTORABLE_RE.search(text)
    if found:
        raise _FrontmatterError(f"frontmatter contains U+{ord(found.group()):04X}")
    return text


def _scalar_text(value: Any) -> str | None:
    """A scalar frontmatter value as text; None for null, lists and mappings."""
    if value is None or isinstance(value, list | dict):
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _read_type(value: Any) -> tuple[str, bool]:
    """2.10: a non-empty string is trimmed and lower-cased; anything else is `note`.

    The flag is W4 (2.11): a string other than the six known types and `note`.
    """
    if isinstance(value, str) and value.strip():
        note_type = value.strip().lower()
        unknown = note_type not in conventions.KNOWN_TYPES and note_type != conventions.DEFAULT_TYPE
        return note_type, unknown
    return conventions.DEFAULT_TYPE, False


def _read_date(value: Any) -> tuple[date | None, bool]:
    """2.10 date rule: (the date or None, whether a present value was invalid)."""
    if value is None:
        return None, False
    if isinstance(value, TaggedScalar) and str(value.tag) == _STR_TAG:
        value = str(value.value)  # `!!str 2026-10-09` is a string for every rule
    if isinstance(value, _YamlTimestamp):
        if isinstance(value.parsed, datetime):
            return value.parsed.date(), False  # the date as written, no timezone conversion
        return value.parsed, False
    if isinstance(value, str) and _ISO_DATE_RE.fullmatch(value):
        try:
            return date.fromisoformat(value), False
        except ValueError:
            return None, True
    return None, True


def _frontmatter_links(frontmatter: dict[str, Any]) -> set[str]:
    """2.8: links in every string value of the frontmatter, at any depth (not keys)."""
    targets: set[str] = set()
    pending: list[Any] = [frontmatter]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
        elif isinstance(value, str):
            targets |= link_targets(value)
    return targets


def _is_tag_character(char: str) -> bool:
    # 2.10: letters (L*), combining marks (M*), decimal digits (Nd), `_`, `-` and `/`.
    category = unicodedata.category(char)
    return char in "_-/" or category[0] in "LM" or category == "Nd"


def _tag_from_token(token: str) -> str | None:
    """Apply the 2.10 token rules; return the stored tag, or None when not a tag."""
    token = token.rstrip("/")  # every trailing `/` is stripped
    if not token or not all(_is_tag_character(char) for char in token):
        return None
    if all(char == "/" or unicodedata.category(char) == "Nd" for char in token):
        return None  # needs a character that is neither a digit nor `/`
    return token.lower()


def _inline_tags(body: str) -> set[str]:
    """2.10 inline tags: body only, outside code and outside the whole text of wikilinks."""
    text = WIKILINK_RE.sub(MASK_PLACEHOLDER, mask_code(unicodedata.normalize("NFC", body)))
    tags = set()
    for start in _TAG_START_RE.finditer(text):
        end = start.end()
        while end < len(text) and _is_tag_character(text[end]):
            end += 1
        tag = _tag_from_token(text[start.end() : end])
        if tag is not None:
            tags.add(tag)
    return tags


def _frontmatter_tags(value: Any) -> tuple[set[str], tuple[str, ...]]:
    """2.10 frontmatter `tags`: a list, or a single string split on commas.

    Returns the valid tags and the items dropped as invalid. Empty and null items
    are skipped, not reported as dropped. A mapping is one dropped item.
    """
    if value is None:
        return set(), ()
    if isinstance(value, dict):
        return set(), (str(value),)
    if isinstance(value, list):
        # Each item converted to a string; a nested list or mapping becomes its repr
        # and is dropped as invalid.
        items = [_scalar_text(item) or str(item) for item in value if item is not None]
    else:
        items = str(_scalar_text(value)).split(",")
    tags: set[str] = set()
    dropped: list[str] = []
    for item in items:
        item = item.strip()
        if not item:
            continue
        tag = _tag_from_token(unicodedata.normalize("NFC", item.removeprefix("#")))
        if tag is None:
            dropped.append(item)
        else:
            tags.add(tag)
    return tags, tuple(dropped)
