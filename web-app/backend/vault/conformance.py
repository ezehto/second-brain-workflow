"""Vault conformance checker (plan section 2.11, task P1-08).

Usage: python -m vault.conformance <vault path>

Walks a vault, parses every non-ignored note with `vault.parser.parse_note` and
reports one line per note and code: `<code> <vault-relative path>: <message>`,
sorted by path then code. Failures (F1 to F8) make the exit code 1; warnings
(W1 to W6) are printed and never change it. A path that is not a directory is a
usage error (exit code 2, message on stderr). The vault is only ever read.

Every rule comes from `vault.conventions`, `vault.parser`, `vault.links` or
`vault.slug`; this module only decides which notes get which check.
"""

import argparse
import os
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

from vault import conventions
from vault.ignore import iter_note_paths as note_paths
from vault.links import find_wikilinks, normalize_target, resolve_link, split_wikilink
from vault.parser import ParsedNote, parse_note
from vault.slug import resolve_project

EXIT_OK = 0
EXIT_FAILURES = 1
EXIT_USAGE = 2

LINK_KEYS = ("project", "triaged_to")  # W3: frontmatter keys whose links must not be ambiguous


@dataclass(frozen=True, order=True)
class Finding:
    """One problem: ordering is path, then code, which is the output order."""

    path: str
    code: str
    message: str


@dataclass(frozen=True)
class Context:
    """What a per-note check needs to know about the rest of the vault."""

    note_paths: tuple[str, ...]  # every non-ignored `.md` file
    project_paths: tuple[str, ...]  # those whose parsed type is `project`
    id_owners: dict[str, list[str]]  # note id -> the paths that carry it


Check = Callable[[ParsedNote, Context], str | None]


# --- Reading a note (the ignore rules live in vault.ignore) ----------------------------------


def read_note(root: Path, rel: str) -> ParsedNote | None:
    """Parse one note; None when it vanished since it was listed."""
    try:
        data = (root / rel).read_bytes()
    except FileNotFoundError:
        return None
    return parse_note(rel, data)


def escape_text(text: str) -> str:
    """Escape control and non-printable characters (including lone surrogates from
    undecodable file names) so a finding always fits on one line."""
    return "".join(
        char if char.isprintable() else char.encode("unicode_escape", "backslashreplace").decode()
        for char in text
    )


def template_names_on_disk(root: Path) -> set[str]:
    """Casefolded file names in the templates folder, whose folder names match any case."""
    current = root
    for part in conventions.TEMPLATES_FOLDER.split("/"):
        with os.scandir(current) as scan:
            entries = sorted(scan, key=lambda entry: entry.name)
        match = next(
            (
                entry
                for entry in entries
                if entry.name.casefold() == part.casefold() and entry.is_dir(follow_symlinks=False)
            ),
            None,
        )
        if match is None:
            return set()
        current = Path(match.path)
    with os.scandir(current) as scan:
        return {e.name.casefold() for e in scan if e.is_file(follow_symlinks=False)}


# --- The checks, one function per code; each returns a message or None ----------------------


def f1_malformed_frontmatter(note: ParsedNote, ctx: Context) -> str | None:
    return note.parse_error


def f2_missing_required_key(note: ParsedNote, ctx: Context) -> str | None:
    missing = [k for k in conventions.REQUIRED_KEYS[note.type] if note.frontmatter.get(k) is None]
    return f"missing {', '.join(missing)}" if missing else None


def f3_status_outside_vocabulary(note: ParsedNote, ctx: Context) -> str | None:
    if note.unusable_status:
        return "status is a list or mapping, not a single value"
    allowed = conventions.STATUSES.get(note.type)  # daily has none
    if allowed and note.status is not None and note.status not in allowed:
        return f"status {note.status!r} is not one of {', '.join(allowed)}"
    return None


def _daily_path_ok(path: str) -> bool:
    """`01-Daily/YYYY/YYYY-MM-DD.md` with the year folder matching the file name."""
    parts = PurePosixPath(path).parts
    if len(parts) != 3 or parts[0].casefold() != conventions.TYPE_FOLDERS["daily"].casefold():
        return False
    name = parts[2]
    year, stem = parts[1], name[:-3] if name.casefold().endswith(".md") else name
    if not (len(year) == 4 and year.isascii() and year.isdigit()):
        return False
    if len(stem) != 10 or stem[4] != "-" or stem[7] != "-" or stem[:4] != year:
        return False
    try:
        date.fromisoformat(stem)
    except ValueError:
        return False
    return True


def f4_outside_its_folder(note: ParsedNote, ctx: Context) -> str | None:
    if note.type == "daily":
        if _daily_path_ok(note.path):
            return None
        return "a daily note belongs at 01-Daily/YYYY/YYYY-MM-DD.md with a matching year"
    folder = conventions.TYPE_FOLDERS[note.type]
    if note.path.casefold().startswith(folder.casefold() + "/"):
        return None
    return f"a {note.type} note belongs under {folder}/"


def f5_unsafe_file_name(note: ParsedNote, ctx: Context) -> str | None:
    name = PurePosixPath(note.path).name
    unsafe = (
        conventions.CONTROL_CHARACTERS
        | conventions.WINDOWS_ILLEGAL_CHARACTERS
        | conventions.LINK_BREAKING_CHARACTERS
    )
    bad = sorted({char for char in name if char in unsafe})
    if bad:
        return "file name contains " + ", ".join(repr(char) for char in bad)
    if note.title.upper() in conventions.RESERVED_DEVICE_NAMES:
        return f"file name {note.title!r} is a reserved device name"
    return None


def f7_invalid_date(note: ParsedNote, ctx: Context) -> str | None:
    return f"invalid date in {', '.join(note.invalid_dates)}" if note.invalid_dates else None


def f8_invalid_priority(note: ParsedNote, ctx: Context) -> str | None:
    if not note.invalid_priority:
        return None
    value = note.frontmatter.get("priority")
    return f"priority {value!r} is not one of {', '.join(conventions.PRIORITIES)}"


def w1_missing_id(note: ParsedNote, ctx: Context) -> str | None:
    return "no id" if note.note_id is None else None


def w2_duplicate_id(note: ParsedNote, ctx: Context) -> str | None:
    if note.note_id is None:
        return None
    others = [path for path in ctx.id_owners[note.note_id] if path != note.path]
    return f"id {note.note_id} is also used by {', '.join(others)}" if others else None


def w3_ambiguous_link(note: ParsedNote, ctx: Context) -> str | None:
    ambiguous = []
    for key in LINK_KEYS:
        value = note.frontmatter.get(key)
        for item in value if isinstance(value, list) else [value]:
            if not isinstance(item, str):
                continue
            for inner in find_wikilinks(item):
                target = normalize_target(split_wikilink(inner))
                if target is None:
                    continue
                if resolve_link(target, ctx.note_paths).status == "ambiguous":
                    ambiguous.append(f"{key} [[{inner}]]")
    return "ambiguous link: " + ", ".join(ambiguous) if ambiguous else None


def w4_unknown_type(note: ParsedNote, ctx: Context) -> str | None:
    return f"unknown type {note.type!r}" if note.unknown_type else None


def w5_unresolved_project(note: ParsedNote, ctx: Context) -> str | None:
    if note.unusable_project:
        return "project value gives no slug"
    if note.project is None:
        return None
    resolution = resolve_project(note.project, ctx.project_paths)
    if resolution.status == "unknown":
        return f"project {note.project!r} matches no project note"
    if resolution.status == "duplicate":
        return f"project {note.project!r} matches several project notes: " + ", ".join(
            resolution.matches
        )
    return None


def w6_dropped_tags(note: ParsedNote, ctx: Context) -> str | None:
    if not note.dropped_tags:
        return None
    return "invalid tags dropped: " + ", ".join(repr(tag) for tag in note.dropped_tags)


# 2.11: every note gets F1 and F5 (and W4); only notes with a known type and
# readable frontmatter get the rest.
EVERY_NOTE: tuple[tuple[str, Check], ...] = (
    ("F1", f1_malformed_frontmatter),
    ("F5", f5_unsafe_file_name),
    ("W4", w4_unknown_type),
)
KNOWN_TYPE_ONLY: tuple[tuple[str, Check], ...] = (
    ("F2", f2_missing_required_key),
    ("F3", f3_status_outside_vocabulary),
    ("F4", f4_outside_its_folder),
    ("F7", f7_invalid_date),
    ("F8", f8_invalid_priority),
    ("W1", w1_missing_id),
    ("W2", w2_duplicate_id),
    ("W3", w3_ambiguous_link),
    ("W5", w5_unresolved_project),
    ("W6", w6_dropped_tags),
)


def f6_missing_templates(root: Path) -> Iterator[Finding]:
    present = template_names_on_disk(root)
    for name in conventions.TEMPLATE_NAMES:
        rel = f"{conventions.TEMPLATES_FOLDER}/{name}"
        if name.casefold() not in present:
            yield Finding(rel, "F6", "template is missing")


# --- Driver ---------------------------------------------------------------------------------


def check_vault(root: Path) -> list[Finding]:
    """All findings for the vault at `root`, sorted by path then code."""
    parsed_or_none = (read_note(root, rel) for rel in note_paths(root))
    notes = [parsed for parsed in parsed_or_none if parsed is not None]
    id_owners: dict[str, list[str]] = {}
    for parsed in notes:
        if parsed.note_id is not None:
            id_owners.setdefault(parsed.note_id, []).append(parsed.path)
    ctx = Context(
        note_paths=tuple(parsed.path for parsed in notes),
        project_paths=tuple(p.path for p in notes if p.type == "project"),
        id_owners=id_owners,
    )

    findings = list(f6_missing_templates(root))
    for parsed in notes:
        known = parsed.parse_error is None and parsed.type in conventions.KNOWN_TYPES
        checks = EVERY_NOTE + KNOWN_TYPE_ONLY if known else EVERY_NOTE
        for code, check in checks:
            message = check(parsed, ctx)
            if message is not None:
                findings.append(Finding(parsed.path, code, " ".join(escape_text(message).split())))
    return sorted(findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m vault.conformance",
        description="Check a vault against the conventions; read-only.",
    )
    parser.add_argument("vault", help="path of the vault directory")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # odd file names must never crash the output
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    root = Path(args.vault)
    if not root.is_dir():
        print(f"error: {args.vault} is not a directory", file=sys.stderr)
        return EXIT_USAGE
    try:
        findings = check_vault(root)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    for finding in findings:
        print(f"{finding.code} {escape_text(finding.path)}: {finding.message}")
    failed = any(finding.code.startswith("F") for finding in findings)
    return EXIT_FAILURES if failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
