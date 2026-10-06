"""Read-side queries over the index (plan sections 2.1, 2.8, 2.9, 2.10, 5).

Pure helpers used by the API views: filtering and ordering notes, resolving links and backlinks
at query time, resolving project slugs and assembling the dashboard. Nothing here writes to the
database or the vault. "Today" is always passed in by the caller (`vault.clock.today()`), so a
test can pin it.

Every ordering ends with `path`, compared with the `C` collation so the order is bytewise and
does not depend on the database's locale.
"""

import logging
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db.models import F, Q, QuerySet
from django.db.models.functions import Collate, Lower

from vault import conventions
from vault.links import (
    LinkResolution,
    find_wikilinks,
    normalize_target,
    resolve_link,
    split_wikilink,
)
from vault.models import Link, Note
from vault.parser import _tag_from_token
from vault.slug import project_note_slug

logger = logging.getLogger(__name__)

# A task in one of these statuses is finished: never open, never overdue.
TERMINAL_STATUSES = ("done", "cancelled")

# Rows in the dashboard's recent activity and a project's recent notes.
RECENT_LIMIT = 10

PATH_ORDER = Collate("path", "C")
_TITLE_ORDER = Collate(Lower("title"), "C")


# --- notes: filtering and ordering --------------------------------------------------------


def with_tags(queryset: QuerySet[Note]) -> QuerySet[Note]:
    """Prefetch the tags a note summary shows (one extra query for the whole page)."""
    return queryset.prefetch_related("tags")


def normalize_tag(value: str) -> str | None:
    """A tag as the parser stores it: one leading `#` dropped, NFC, trailing `/` stripped,
    lower-cased; None when the text is not a valid tag (then it matches nothing)."""
    return _tag_from_token(unicodedata.normalize("NFC", value.strip().removeprefix("#")))


def overdue_q(today: date) -> Q:
    """A valid `due` before today on a note that is not finished (2.10: null `due` never)."""
    return Q(due__lt=today) & ~Q(status__in=TERMINAL_STATUSES)


def filter_notes(
    queryset: QuerySet[Note], params: Mapping[str, Any], today: date
) -> QuerySet[Note]:
    """Apply the validated list filters of `GET /api/notes/`; they combine with AND.

    `due_before` and `due_after` are inclusive. `overdue` is generic: any type with a past `due`
    and a status that is not `done` or `cancelled` (a note with no status counts).
    A note whose `due` is null, absent or invalid matches none of `overdue=true`, `due_before`
    and `due_after`.
    """
    if "type" in params:
        queryset = queryset.filter(type=params["type"])
    if params.get("status"):
        queryset = queryset.filter(status__in=params["status"])
    if "priority" in params:
        queryset = queryset.filter(priority=params["priority"])
    if "project" in params:
        queryset = queryset.filter(project=params["project"])
    if "tag" in params:
        tag = normalize_tag(params["tag"])
        queryset = queryset.filter(tags__name=tag) if tag else queryset.none()
    if "due_before" in params:
        queryset = queryset.filter(due__lte=params["due_before"])
    if "due_after" in params:
        queryset = queryset.filter(due__gte=params["due_after"])
    if "overdue" in params:
        condition = overdue_q(today)
        queryset = queryset.filter(condition if params["overdue"] else ~condition)
    if "path_prefix" in params:
        queryset = queryset.filter(path__startswith=params["path_prefix"])
    if "has_parse_error" in params:
        queryset = queryset.filter(parse_error__isnull=not params["has_parse_error"])
    return queryset


def order_notes(queryset: QuerySet[Note], ordering: str = "-modified") -> QuerySet[Note]:
    """Order by `-modified` (newest file first), `due` (no valid due last), `title`, `path`
    or `-path`.

    Every ordering ends with `path`.
    """
    if ordering == "-modified":
        keys = [F("file_mtime").desc(), PATH_ORDER]
    elif ordering == "due":
        keys = [F("due").asc(nulls_last=True), PATH_ORDER]
    elif ordering == "title":
        keys = [_TITLE_ORDER.asc(), PATH_ORDER]
    elif ordering == "path":
        keys = [PATH_ORDER]
    elif ordering == "-path":
        keys = [PATH_ORDER.desc()]
    else:
        raise ValueError(f"unknown ordering {ordering!r}")
    return queryset.order_by(*keys)


def task_sort_key(note: Note) -> tuple:
    """`due` ascending (no valid due last), then title, then path (the dashboard's order)."""
    return (note.due is None, note.due or date.min, note.title.lower(), note.path)


# --- notes: links and backlinks -----------------------------------------------------------


def all_paths() -> list[str]:
    """Every indexed path, the universe link resolution runs against (2.8)."""
    return list(Note.objects.order_by(PATH_ORDER).values_list("path", flat=True))


def _strings(value: Any) -> Iterable[str]:
    """Every string value of a frontmatter structure (keys are not scanned, as in 2.8)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


def written_targets(note: Note) -> list[str]:
    """Each distinct link target spelled as written, in body then frontmatter order.

    Display text and heading are dropped; links to the same note (`[[#H]]`) and attachments
    are not stored by the indexer and so are not listed.
    """
    texts = [note.body, *_strings(note.frontmatter)]
    spellings: dict[str, None] = {}
    for text in texts:
        for inner in find_wikilinks(text):
            raw = split_wikilink(inner)
            if normalize_target(raw) is not None:
                spellings[raw.strip()] = None
    return list(spellings)


def _link_entry(resolution: LinkResolution) -> dict[str, str | None]:
    return {"path": resolution.path, "state": resolution.status}


def resolve_links(note: Note, paths: list[str] | None = None) -> dict[str, dict]:
    """Map each link target as written to `{path, state}` (2.8, resolved at query time).

    `state` is `resolved`, `ambiguous` (`path` is the shortest-path match, ties by path order)
    or `unresolved` (`path` is null).
    """
    paths = all_paths() if paths is None else paths
    links = {}
    for spelling in written_targets(note):
        target = normalize_target(spelling)
        if target is not None:
            links[spelling] = _link_entry(resolve_link(target, paths))
    return links


def _path_keys(path: str) -> set[str]:
    """The normalised targets that can name a note: its stem and every folder-qualified tail."""
    segments = path.split("/")
    keys = {normalize_target("/".join(segments[start:])) for start in range(len(segments))}
    return {key for key in keys if key}


def backlinks(note: Note, paths: list[str] | None = None) -> list[dict[str, str]]:
    """Notes whose links resolve to `note`, by path. An ambiguous link counts for the one
    note it resolves to, not for every candidate (2.8 rule 4)."""
    paths = all_paths() if paths is None else paths
    candidates = (
        Link.objects.filter(target_title__in=_path_keys(note.path))
        .exclude(source_id=note.pk)
        .values_list("target_title", "source__path", "source__title")
    )
    found: dict[str, str] = {}
    resolved: dict[str, str | None] = {}
    for target, source_path, source_title in candidates:
        if target not in resolved:
            resolved[target] = resolve_link(target, paths).path
        if resolved[target] == note.path:
            found[source_path] = source_title
    return [{"path": path, "title": found[path]} for path in sorted(found, key=str.encode)]


def attach_detail(note: Note, paths: list[str] | None = None) -> Note:
    """Set what `NoteDetailSerializer` reads beyond the columns: `backlinks`, `resolved_links`."""
    paths = all_paths() if paths is None else paths
    note.backlinks = backlinks(note, paths)
    note.resolved_links = resolve_links(note, paths)
    return note


# --- projects (2.1) -----------------------------------------------------------------------


def _section_text(body: str, heading: str) -> str | None:
    """The text under `## <heading>` up to the next heading, or None when empty or absent."""
    match = re.search(
        rf"^##[ \t]+{re.escape(heading)}[ \t]*\n(.*?)(?=^#{{1,6}}[ \t]|\Z)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    return (match.group(1).strip() or None) if match else None


def project_notes() -> list[Note]:
    """Every `type: project` note, by path."""
    return list(Note.objects.filter(type="project").order_by(PATH_ORDER))


def project_slugs(notes: list[Note]) -> tuple[dict[str, Note], set[str]]:
    """(slug -> note for slugs of exactly one project note, the slugs several notes share).

    Two project notes with the same slug resolve to neither (2.1); the Index Status page lists
    them under "duplicate project slugs".
    """
    by_slug: dict[str, list[Note]] = {}
    for note in notes:
        by_slug.setdefault(project_note_slug(note.path), []).append(note)
    unique = {slug: group[0] for slug, group in by_slug.items() if len(group) == 1}
    return unique, {slug for slug, group in by_slug.items() if len(group) > 1}


def open_tasks() -> QuerySet[Note]:
    """Every task that is not done or cancelled (a task with an unknown status is open)."""
    return Note.objects.filter(type="task").exclude(status__in=TERMINAL_STATUSES)


def open_task_counts() -> Counter[str]:
    """Open tasks per project slug."""
    return Counter(
        slug for slug in open_tasks().values_list("project", flat=True) if slug is not None
    )


def project_summary(note: Note, resolved: Mapping[str, Note], counts: Counter[str]) -> dict:
    """The `ProjectSummary` payload; a project whose slug is shared has no tasks (unresolved)."""
    slug = project_note_slug(note.path)
    counted = resolved.get(slug) is note
    return {
        "slug": slug,
        "title": note.title,
        "path": note.path,
        "status": note.status,
        "goal": _section_text(note.body, "Goal"),
        "open_task_count": counts[slug] if counted else 0,
        "modified": note.file_mtime,
    }


def project_list() -> list[dict]:
    """Every project note as a summary, by path."""
    notes = project_notes()
    resolved, _ = project_slugs(notes)
    counts = open_task_counts()
    return [project_summary(note, resolved, counts) for note in notes]


def project_detail(slug: str) -> dict | None:
    """The `ProjectDetail` payload, or None for an unknown or duplicated slug."""
    notes = project_notes()
    resolved, _ = project_slugs(notes)
    note = resolved.get(slug)
    if note is None:
        return None
    members = with_tags(Note.objects.filter(project=slug))
    tasks = sorted(with_tags(open_tasks().filter(project=slug)), key=task_sort_key)
    return {
        "project": project_summary(note, resolved, Counter({slug: len(tasks)})),
        "note": attach_detail(note),
        "open_tasks": tasks,
        "decisions": list(order_notes(members.filter(type="decision"), "-modified")),
        "recent_notes": list(order_notes(members.exclude(pk=note.pk), "-modified")[:RECENT_LIMIT]),
    }


# --- dashboard ----------------------------------------------------------------------------


def daily_note_path(today: date) -> str:
    """`01-Daily/YYYY/YYYY-MM-DD.md`, where today's daily note lives (design D)."""
    return f"{conventions.TYPE_FOLDERS['daily']}/{today:%Y}/{today.isoformat()}.md"


def is_untouched_daily(note: Note, today: date) -> bool:
    """Whether today's daily note still equals the rendered template (2.2). False when the file
    or the template cannot be read: the note is then not offered for filling."""
    # Imported here: the writer is a heavy module the other queries do not need.
    from vault.templating import TemplateError, load_template
    from vault.writer import is_untouched

    root = Path(settings.VAULT_ROOT)
    try:
        text = (root / note.path).read_text(encoding="utf-8")
        return is_untouched(text, load_template(root, "daily"), today)
    except (OSError, UnicodeDecodeError, TemplateError) as exc:
        logger.warning("cannot judge %s untouched: %s", note.path, type(exc).__name__)
        return False


def standup_today(today: date, note: Note | None) -> dict:
    """Today's standup: the daily note (None when it does not exist) or the carry-forward
    preview of what starting the standup would write (2.2)."""
    if note is None:
        # Imported here: carry_forward uses this module's helpers.
        from vault.carry_forward import preview

        return {"exists": False, "preview": preview(today)}
    return {
        "exists": True,
        "note": attach_detail(note),
        "untouched": is_untouched_daily(note, today),
    }


def dashboard(today: date) -> dict:
    """The dashboard sections, except the index summary.

    One query (plus one for tags) reads the open tasks, the project notes and today's daily
    note; the sections are cut from it in Python. Today's tasks are open tasks due today,
    overdue are open tasks due before today; those two, in progress and blocked are ordered by
    `due` (no valid due last), title, path.
    """
    daily = daily_note_path(today)
    rows = list(
        with_tags(
            Note.objects.filter(
                (Q(type="task") & ~Q(status__in=TERMINAL_STATUSES))
                | Q(type="project")
                | Q(path=daily)
            )
        )
    )
    tasks = sorted((n for n in rows if n.type == "task"), key=task_sort_key)
    projects = sorted((n for n in rows if n.type == "project"), key=lambda n: n.path.encode())
    resolved, _ = project_slugs(projects)
    counts = Counter(task.project for task in tasks if task.project is not None)
    return {
        "today": today,
        "today_tasks": [task for task in tasks if task.due == today],
        "in_progress": [task for task in tasks if task.status == "in-progress"],
        "blocked": [task for task in tasks if task.status == "blocked"],
        "overdue": [task for task in tasks if task.due is not None and task.due < today],
        "standup": standup_today(today, next((n for n in rows if n.path == daily), None)),
        "recent_activity": list(
            order_notes(with_tags(Note.objects.all()), "-modified")[:RECENT_LIMIT]
        ),
        "active_projects": [
            project_summary(note, resolved, counts) for note in projects if note.status == "active"
        ],
        "inbox_count": Note.objects.filter(type="capture", status="inbox").count(),
    }
