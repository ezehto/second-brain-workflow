"""Project slugs (plan section 2.1).

`project_slug` turns a frontmatter `project` value into the indexed slug;
`resolve_project` matches a slug against the project notes, which needs the set
of project note paths and so is not the parser's job.
"""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from vault.links import WIKILINK_RE, note_stem, split_wikilink

_NON_SLUG_RUN_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class ProjectResolution:
    """Outcome of matching a project slug against the project notes."""

    status: str  # "resolved", "duplicate" or "unknown"
    path: str | None  # the project note, only when exactly one matches
    matches: tuple[str, ...]  # every project note with this slug, sorted


def slugify(text: str) -> str:
    """NFKD, drop combining marks, lower-case, runs outside [a-z0-9] to `-`, trim `-`."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _NON_SLUG_RUN_RE.sub("-", without_marks.lower()).strip("-")


def project_note_slug(path: str) -> str:
    """The slug of a project note: `slugify` of its file name stem."""
    return slugify(note_stem(path))


def project_slug(value: str) -> str | None:
    """The indexed `project` value: a slug, or None when the value gives no slug.

    A whole-value wikilink loses its brackets, display text, heading and folder
    prefix (and a `.md` suffix) before `slugify`; any other value is slugified as
    written.
    """
    link = WIKILINK_RE.fullmatch(value.strip())
    text = note_stem(split_wikilink(link.group(1)).replace("\\", "/")) if link else value
    return slugify(text) or None


def resolve_project(slug: str, project_paths: Iterable[str]) -> ProjectResolution:
    """Match a slug against the paths of `type: project` notes (2.1).

    Two or more project notes with the slug resolve to neither.
    """
    matches = tuple(sorted(path for path in project_paths if project_note_slug(path) == slug))
    if not matches:
        return ProjectResolution("unknown", None, ())
    if len(matches) > 1:
        return ProjectResolution("duplicate", None, matches)
    return ProjectResolution("resolved", matches[0], matches)
