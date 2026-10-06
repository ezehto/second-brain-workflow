"""Templates: load from the vault and substitute the placeholder subset (plan section 3.1).

Implemented exactly: `{{title}}`, `{{date}}`, `{{time}}`, `{{date:F}}`, `{{time:F}}`, where F holds
only the tokens YYYY, MM, DD, HH, mm, ss and literal non-letter characters. Any other `{{...}}`
token is a `TemplateError`. The template source is the vault's own copy (2.9), never the seed.
"""

import os
import re
import stat
from datetime import datetime
from pathlib import Path

from vault import conventions
from vault.sanitize import WriterError

TEMPLATE_SUFFIX = ".md"

_PLACEHOLDER_RE = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
_FORMAT_TOKENS = {
    "YYYY": "%Y",
    "MM": "%m",
    "DD": "%d",
    "HH": "%H",
    "mm": "%M",
    "ss": "%S",
}
_DEFAULT_FORMATS = {"date": "YYYY-MM-DD", "time": "HH:mm"}


class TemplateError(ValueError, WriterError):
    """A template is missing, unreadable, or holds a placeholder outside the subset."""


def find_child_ci(directory: Path, name: str) -> Path | None:
    """The entry of `directory` named `name` in any letter case (the vault's drive is
    case-insensitive), preferring an exact match; None when there is none."""
    folded = name.casefold()
    match = None
    with os.scandir(directory) as scan:
        for entry in scan:
            if entry.name == name:
                return Path(entry.path)
            if match is None and entry.name.casefold() == folded:
                match = Path(entry.path)
    return match


def load_template(root: Path, note_type: str) -> str:
    """Read `<root>/08-System/Templates/<type>.md`: UTF-8, BOM dropped, LF line endings.

    Symlinks anywhere on the path are refused.
    """
    name = f"{note_type}{TEMPLATE_SUFFIX}"
    if name not in conventions.TEMPLATE_NAMES:
        raise TemplateError(f"there is no template for type {note_type!r}")
    current = root
    for part in conventions.TEMPLATES_FOLDER.split("/"):
        found = find_child_ci(current, part) if current.is_dir() else None
        if found is None or found.is_symlink() or not found.is_dir():
            raise TemplateError(f"template folder {conventions.TEMPLATES_FOLDER} is missing")
        current = found
    path = find_child_ci(current, name)
    if path is None:
        raise TemplateError(f"template {name} is missing")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise TemplateError(f"template {name} cannot be read: {exc.strerror}") from exc
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise TemplateError(f"template {name} is not a regular file")
        data = handle.read()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TemplateError(f"template {name} is not valid UTF-8") from exc
    return text.replace("\r\n", "\n")


def _format_moment(pattern: str, when: datetime, token: str) -> str:
    """Render a `{{date:F}}` / `{{time:F}}` pattern; reject anything outside the subset."""
    if not pattern:
        raise TemplateError(f"{{{{{token}}}}} has an empty format")
    parts: list[str] = []
    position = 0
    while position < len(pattern):
        char = pattern[position]
        if char.isalpha():
            # A maximal run of one letter must be exactly one supported token (`MMMM` is not).
            end = position
            while end < len(pattern) and pattern[end] == char:
                end += 1
            run = pattern[position:end]
            if run not in _FORMAT_TOKENS:
                raise TemplateError(f"{{{{{token}}}}} uses {run!r}, which is outside the subset")
            parts.append(when.strftime(_FORMAT_TOKENS[run]))
            position = end
        elif char in "[]":  # Moment.js escape syntax
            raise TemplateError(f"{{{{{token}}}}} uses {char!r}, which is outside the subset")
        else:
            parts.append(char)
            position += 1
    return "".join(parts)


def render(template: str, *, title: str, when: datetime) -> str:
    """Substitute the placeholder subset in one pass; text substituted in is never re-scanned."""

    def substitute(match: re.Match[str]) -> str:
        token = match.group(1)
        if token == "title":
            return title
        kind, colon, pattern = token.partition(":")
        if kind in _DEFAULT_FORMATS and (colon or token == kind):
            return _format_moment(pattern if colon else _DEFAULT_FORMATS[kind], when, token)
        raise TemplateError(f"unsupported placeholder {{{{{token}}}}}")

    return _PLACEHOLDER_RE.sub(substitute, template)
