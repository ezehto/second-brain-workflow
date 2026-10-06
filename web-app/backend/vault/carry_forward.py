"""Standup carry-forward (plan section 2.2): what goes under each heading of today's daily note.

`carry_items` is a pure function of the previous daily note's body and the indexed task and
project notes; `preview` loads those from the index. Nothing here reads or writes the vault or
the database beyond the index queries of `preview`, so the result is the one the standup
endpoint writes and the dashboard shows. Every ordering ends with the note's path.
"""

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import date

from vault import conventions, queries
from vault.links import find_wikilinks, mask_code, normalize_target, resolve_link, split_wikilink
from vault.models import Note
from vault.writer import heading_positions

# Task statuses carried under Today, in this order. `planned` only when due on or before today.
TODAY_STATUSES = ("in-progress", "review", "planned")

_UNCHECKED_RE = re.compile(r"[ \t]*[-*+] \[ \] (.*)")
_DAILY_PATH_RE = re.compile(r"01-Daily/\d{4}/(\d{4}-\d{2}-\d{2})\.md", re.ASCII)
_UNSAFE_STEM_CHARS = frozenset("$`<>")  # a link to such a note is always folder-qualified
_WHITESPACE_RE = re.compile(r"\s+")


def section_lines(body: str, heading: str) -> list[str]:
    """The lines under the first `## <heading>` of `body`, up to the next heading of level 2 or
    above; fenced code is skipped. Headings are found by the writer's rules (2.4 rules 1 to 3)."""
    lines = body.split("\n")
    headings = heading_positions(lines)
    folded = heading.casefold()
    start = next((h[0] for h in headings if h[1] == 2 and h[2] == folded), None)
    if start is None:
        return []
    end = next((h[0] for h in headings if h[0] > start and h[1] <= 2), len(lines))
    masked = mask_code(body).split("\n")
    return [
        line.rstrip("\r")
        for line, shown in zip(lines[start + 1 : end], masked[start + 1 : end], strict=True)
        if not line.strip() or shown.strip()  # a fenced line is not content
    ]


def unchecked_items(body: str, heading: str) -> list[str]:
    """Every unchecked `- [ ] ` item (also `*` and `+`, any indentation) under `## <heading>`,
    verbatim and in order."""
    return [line for line in section_lines(body, heading) if _UNCHECKED_RE.fullmatch(line)]


def _text_key(line: str) -> str:
    match = _UNCHECKED_RE.fullmatch(line)
    assert match is not None
    return _WHITESPACE_RE.sub(" ", match.group(1)).strip()


def _blocked_by(task: Note) -> str | None:
    value = task.frontmatter.get("blocked_by")
    # `blocked_by: [[Task]]` parses as a nested list: a one-item list stands for its item.
    while isinstance(value, list) and len(value) == 1:
        value = value[0]
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        return None
    return _WHITESPACE_RE.sub(" ", str(value)).strip() or None


class _Links:
    """Emitted links (2.5): bare when the file name stem is unique among the indexed notes,
    folder-qualified otherwise."""

    def __init__(self, paths: Iterable[str]) -> None:
        self._stems = Counter(_stem(path).casefold() for path in paths)

    def to(self, path: str) -> str:
        target = path.removesuffix(".md")
        stem = _stem(path)
        if self._stems[stem.casefold()] > 1 or _UNSAFE_STEM_CHARS & set(stem):
            return f"[[{target}]]"
        return f"[[{stem}]]"


def _stem(path: str) -> str:
    return path.rpartition("/")[2].removesuffix(".md")


def _links_a_task(line: str, paths: Sequence[str], task_paths: frozenset[str]) -> bool:
    """Whether `line` has a wikilink that resolves (2.8, ambiguous included) to a task note."""
    for inner in find_wikilinks(line):
        target = normalize_target(split_wikilink(inner))
        if target is None:
            continue
        chosen = resolve_link(target, paths).path
        if chosen in task_paths:
            return True
    return False


def carry_items(
    previous_body: str | None,
    tasks: Iterable[Note],
    projects: Mapping[str, Note],
    paths: Sequence[str],
    today: date,
) -> dict[str, list[str]]:
    """The six sections of 2.2 as complete lines, in template order.

    `previous_body` is the body of the previous daily note (None when there is none), `tasks`
    every task note (any status), `projects` the resolved project notes by slug (as
    `queries.project_slugs` returns them) and `paths` every indexed path (link resolution and
    link spelling).
    """
    tasks = list(tasks)
    links = _Links(paths)
    task_paths = frozenset(task.path for task in tasks)

    def by_status(status: str) -> list[Note]:
        chosen = [t for t in tasks if t.status == status]
        if status == "planned":
            chosen = [t for t in chosen if t.due is not None and t.due <= today]
        return sorted(chosen, key=queries.task_sort_key)

    today_tasks = [task for status in TODAY_STATUSES for task in by_status(status)]
    blocked = by_status("blocked")

    today_lines = [f"- [ ] {links.to(task.path)}" for task in today_tasks]
    seen: set[str] = set()
    for line in unchecked_items(previous_body or "", "Today"):
        key = _text_key(line)
        if key in seen or _links_a_task(line, paths, task_paths):
            continue
        seen.add(key)
        today_lines.append(line)

    blocker_lines = []
    for task in blocked:
        reason = _blocked_by(task)
        blocker_lines.append(
            f"- {links.to(task.path)}" + (f" (blocked by: {reason})" if reason else "")
        )

    follow_ups: list[str] = []
    seen = set()
    for line in unchecked_items(previous_body or "", "Follow-ups"):
        key = _text_key(line)
        if key not in seen:
            seen.add(key)
            follow_ups.append(line)

    related = {
        projects[task.project].path: projects[task.project]
        for task in [*today_tasks, *blocked]
        if task.project in projects
    }
    related_lines = [
        f"- {links.to(project.path)}"
        for project in sorted(related.values(), key=lambda p: (p.title.lower(), p.path))
    ]

    sections = {
        "Done": [],
        "Today": today_lines,
        "Blockers": blocker_lines,
        "Decisions / Updates": [],
        "Follow-ups": follow_ups,
        "Related Tasks / Projects": related_lines,
    }
    return {heading: sections[heading] for heading in conventions.STANDUP_HEADINGS}


def _previous_daily_path(paths: Iterable[str], today: date) -> str | None:
    best: tuple[date, str] | None = None
    for path in paths:
        match = _DAILY_PATH_RE.fullmatch(path)
        if match is None:
            continue
        try:
            when = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if when < today and (best is None or (when, path) > best):
            best = (when, path)
    return best[1] if best else None


def preview(today: date) -> dict[str, list[str]]:
    """What starting the standup writes for `today`, from the index as it is now.

    Three queries: every path, the task and project notes, and the previous daily note's body.
    """
    paths = list(Note.objects.values_list("path", flat=True))
    notes = list(Note.objects.filter(type__in=("task", "project")))
    resolved, _ = queries.project_slugs([n for n in notes if n.type == "project"])
    previous = _previous_daily_path(paths, today)
    body = (
        Note.objects.filter(path=previous).values_list("body", flat=True).first()
        if previous
        else None
    )
    tasks = [n for n in notes if n.type == "task"]
    return carry_items(body, tasks, resolved, paths, today)
