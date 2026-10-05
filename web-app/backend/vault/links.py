"""Wikilink extraction, normalisation and resolution (plan section 2.8).

Extraction and normalisation are per note; resolution needs the set of indexed
note paths and is a pure function of it, so the indexer, the checker and the API
share one implementation.
"""

import bisect
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from vault.conventions import ATTACHMENT_EXTENSIONS

# A wikilink or embed on one line: `[[inner]]` or `![[inner]]`.
WIKILINK_RE = re.compile(r"!?\[\[([^\[\]\n]*)\]\]")

# Stands in for masked inline code and, when scanning for tags, for a whole
# wikilink: not whitespace and not a tag character, so a `#` straight after it is
# not taken as a tag (2.10). U+FFFC OBJECT REPLACEMENT CHARACTER.
MASK_PLACEHOLDER = "\ufffc"

# 2.10 "Code regions": a fence opens and closes at any indentation of spaces or tabs
# and after any blockquote markers (`>`), so fences inside lists, quotes and
# Obsidian callouts count. A backtick fence's opening line has no further
# backtick, so ```code``` starting a line is an inline span, not a fence; tilde
# fences have no such limit.
_FENCE_PREFIX = r"^[ \t]*(?:>[ \t]*)*"
_FENCE_OPEN_RE = re.compile(_FENCE_PREFIX + r"(`{3,}(?=[^`]*$)|~{3,})")
_FENCE_CLOSE_RE = re.compile(_FENCE_PREFIX + r"(`{3,}|~{3,})[ \t]*$")
_BACKTICK_RUN_RE = re.compile(r"`+")
_BLANK_LINE_RE = re.compile(r"\n[ \t\r]*\n")
_WHITESPACE_RUN_RE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class LinkResolution:
    """Outcome of resolving one normalised target against the indexed notes."""

    status: str  # "resolved", "ambiguous" or "unresolved"
    path: str | None  # the chosen note's vault-relative path
    matches: tuple[str, ...]  # every matching path, shortest first


def mask_code(text: str) -> str:
    """Blank out fenced code blocks and inline code spans, keeping every line break."""
    return _mask_inline_code(_mask_fences(text))


def _mask_fences(text: str) -> str:
    lines = text.split("\n")
    fence: str | None = None  # the opening fence run while inside a block
    for index, line in enumerate(lines):
        content = line.rstrip("\r")
        if fence is None:
            opened = _FENCE_OPEN_RE.match(content)
            if opened:
                fence = opened.group(1)
                lines[index] = ""
        else:
            closed = _FENCE_CLOSE_RE.match(content)
            if closed and closed.group(1)[0] == fence[0] and len(closed.group(1)) >= len(fence):
                fence = None
            lines[index] = ""
    # An unclosed fence runs to the end of the text.
    return "\n".join(lines)


def _mask_inline_code(text: str) -> str:
    # A run of N backticks opens a span that ends at the next run of exactly N
    # backticks in the same paragraph; an unmatched run is literal text.
    paragraph_ends = [blank.start() for blank in _BLANK_LINE_RE.finditer(text)] + [len(text)]
    parts: list[str] = []
    position = 0
    while opening := _BACKTICK_RUN_RE.search(text, position):
        limit = paragraph_ends[bisect.bisect_left(paragraph_ends, opening.end())]
        closing = next(
            (
                run
                for run in _BACKTICK_RUN_RE.finditer(text, opening.end(), limit)
                if len(run.group()) == len(opening.group())
            ),
            None,
        )
        if closing is None:
            parts.append(text[position : opening.end()])
            position = opening.end()
        else:
            parts.append(text[position : opening.start()] + MASK_PLACEHOLDER)
            position = closing.end()
    parts.append(text[position:])
    return "".join(parts)


def find_wikilinks(text: str) -> list[str]:
    """Return the inner text of every wikilink and embed outside code, as written, in order."""
    return [match.group(1) for match in WIKILINK_RE.finditer(mask_code(text))]


def split_wikilink(inner: str) -> str:
    """Return the raw target of a wikilink's inner text: display text and heading dropped."""
    target, pipe, _ = inner.partition("|")
    if pipe and target.endswith("\\"):
        target = target[:-1]  # `[[A\|alias]]`, the escaped pipe used inside tables
    return target.partition("#")[0]


def _normalise_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\\", "/")
    return _WHITESPACE_RUN_RE.sub(" ", text).strip().casefold()


def normalize_target(raw_target: str) -> str | None:
    """Normalise a raw target to a stored `target_title`, or None when it is not stored.

    None for a link to the same note (`[[#H]]`) and for an attachment: a final
    path segment ending in one of `ATTACHMENT_EXTENSIONS`. Any other dotted name
    is a note title.
    """
    target = _normalise_text(raw_target)
    if target.endswith(".md"):
        target = target[: -len(".md")].rstrip()
    else:
        _, dot, extension = target.rpartition("/")[2].rpartition(".")
        if dot and extension in ATTACHMENT_EXTENSIONS:  # casefolded above
            return None
    return target or None


def link_targets(text: str) -> set[str]:
    """Return the link set of a text: one entry per distinct normalised target."""
    targets = (normalize_target(split_wikilink(inner)) for inner in find_wikilinks(text))
    return {target for target in targets if target is not None}


def _without_md(name: str) -> str:
    return name[: -len(".md")] if name.casefold().endswith(".md") else name


def note_stem(path: str) -> str:
    """The file name of a vault-relative path without `.md`: a note's title (2.9)."""
    return _without_md(path.rpartition("/")[2])


def _note_key(path: str) -> str | None:
    """Normalised vault-relative path without `.md`, or None for a non-note path."""
    if not path.casefold().endswith(".md"):
        return None
    return _normalise_text(_without_md(path))


def resolve_link(target: str, note_paths: Iterable[str]) -> LinkResolution:
    """Resolve a normalised target against the vault-relative paths of indexed notes (2.8)."""
    matches = []
    for path in note_paths:
        key = _note_key(path)
        if key is None:
            continue
        if "/" in target:
            matched = key == target or key.endswith("/" + target)  # rule 1
        else:
            matched = key.rpartition("/")[2] == target  # rule 2
        if matched:
            matches.append(path)
    # Rule 4: shortest path first, ties broken by lexicographic path order.
    ordered = tuple(sorted(matches, key=lambda path: (len(path), path)))
    if not ordered:
        return LinkResolution("unresolved", None, ())
    status = "resolved" if len(ordered) == 1 else "ambiguous"
    return LinkResolution(status, ordered[0], ordered)
