"""Index status and refresh (plan sections 2.7 to 2.10, 2.12)."""

from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from django.conf import settings
from django.db.models import Count
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import (
    INDEX_PROBLEM_CATEGORIES,
    IndexStatusSerializer,
    RefreshSummarySerializer,
)
from vault import clock, conventions, indexer
from vault.dates import frontmatter_date
from vault.links import _note_key
from vault.models import IndexPass, Link, Note
from vault.slug import project_note_slug, resolve_project

Problems = dict[str, list[dict[str, str]]]


def _problem(path: str, detail: str) -> dict[str, str]:
    return {"path": path, "detail": detail}


def ambiguous_targets(targets: Iterable[str], note_paths: Iterable[str]) -> dict[str, int]:
    """Targets that resolve ambiguously (2.8), each with its match count; same rule as
    `resolve_link`, without scanning every note per target.

    A bare target is ambiguous when two or more notes share the file name (a lookup in a
    precomputed stem count); a folder-qualified target scans the precomputed keys.
    """
    keys = [key for key in map(_note_key, note_paths) if key is not None]
    stems = Counter(key.rpartition("/")[2] for key in keys)
    found = {}
    for target in targets:
        if "/" in target:
            count = sum(1 for key in keys if key == target or key.endswith("/" + target))
        else:
            count = stems[target]
        if count > 1:
            found[target] = count
    return found


def _ambiguous_links(note_paths: list[str]) -> list[dict[str, str]]:
    """One entry per source note and ambiguous target."""
    targets = Link.objects.order_by().values_list("target_title", flat=True).distinct()
    ambiguous = ambiguous_targets(targets, note_paths)
    if not ambiguous:
        return []
    sources = Link.objects.filter(target_title__in=ambiguous).values_list(
        "source__path", "target_title"
    )
    return [
        _problem(path, f"[[{target}]] matches {ambiguous[target]} notes")
        for path, target in sorted(sources)
    ]


def compute_problems() -> Problems:
    """The eight problem categories, computed from the index (no stored flags).

    Each entry is `{path, detail}`, ordered by path. Duplicate project slugs list the project
    notes that share a slug; unknown project slugs list the notes that point at no project note.
    """
    rows = list(
        Note.objects.order_by("path").values_list(
            "path", "type", "status", "project", "note_id", "parse_error"
        )
    )
    note_paths = [row[0] for row in rows]
    problems: Problems = {name: [] for name in INDEX_PROBLEM_CATEGORIES}

    ids = defaultdict(list)
    projects = [path for path, note_type, *_ in rows if note_type == "project"]
    slug_groups = defaultdict(list)
    for path in projects:
        slug_groups[project_note_slug(path)].append(path)
    for path, note_type, status, project, note_id, parse_error in rows:
        if parse_error:
            problems["parse_errors"].append(_problem(path, parse_error))
        if note_id is None:
            problems["missing_ids"].append(_problem(path, "no id in the frontmatter"))
        else:
            ids[note_id].append(path)
        vocabulary = conventions.STATUSES.get(note_type)
        if vocabulary and status is not None and status not in vocabulary:
            problems["unknown_statuses"].append(
                _problem(path, f"status '{status}' is not a {note_type} status")
            )
        if project is not None and resolve_project(project, projects).status == "unknown":
            problems["unknown_project_slugs"].append(
                _problem(path, f"project '{project}' matches no project note")
            )
    for note_id, paths in ids.items():
        if len(paths) > 1:
            problems["duplicate_ids"].extend(
                _problem(path, f"id {note_id} is shared by {len(paths)} notes") for path in paths
            )
    for slug, paths in slug_groups.items():
        if len(paths) > 1:
            problems["duplicate_project_slugs"].extend(
                _problem(path, f"slug '{slug}' is shared by {len(paths)} project notes")
                for path in paths
            )
    problems["duplicate_ids"].sort(key=lambda item: item["path"])
    problems["duplicate_project_slugs"].sort(key=lambda item: item["path"])
    problems["ambiguous_links"] = _ambiguous_links(note_paths)
    problems["invalid_dates"] = _invalid_dates()
    return problems


def _invalid_dates() -> list[dict[str, str]]:
    """Notes whose frontmatter holds a date value the 2.10 rule rejected (column null)."""
    candidates = (
        Note.objects.filter(frontmatter__has_any_keys=list(conventions.DATE_KEYS))
        .order_by("path")
        .values_list("path", "frontmatter", "due", "created")
    )
    found = []
    for path, frontmatter, due, created in candidates:
        invalid = [
            key
            for key, column in (("created", created), ("due", due))
            if frontmatter.get(key) is not None and column is None
        ]
        if (
            frontmatter.get("decided") is not None
            and frontmatter_date(frontmatter["decided"]) is None
        ):
            invalid.append("decided")
        if invalid:
            found.append(_problem(path, f"invalid date in {', '.join(invalid)}"))
    return found


def problem_count(problems: Problems) -> int:
    """Entries across every category (the dashboard summary's number)."""
    return sum(len(entries) for entries in problems.values())


def index_status() -> dict:
    """The `IndexStatus` payload."""
    last = IndexPass.objects.filter(pk=IndexPass.SINGLETON_PK).first()
    pinned = clock.pinned_date()
    return {
        "last_pass_at": last.finished_at if last else None,
        "duration_ms": last.duration_ms if last else None,
        "counts_by_type": dict(
            Note.objects.order_by("type").values_list("type").annotate(total=Count("id"))
        ),
        "problems": compute_problems(),
        "test_mode": {"today": pinned} if pinned else None,
    }


def refresh_summary(summary: indexer.PassSummary) -> dict:
    """A pass summary as the `RefreshSummary` payload (`duration_s` becomes `duration_ms`)."""
    data = {key: value for key, value in vars(summary).items() if key != "duration_s"}
    return {"duration_ms": round(summary.duration_s * 1000), **data}


class IndexStatusView(APIView):
    @extend_schema(
        operation_id="index_status",
        tags=["index"],
        summary="Index status",
        responses={200: IndexStatusSerializer},
    )
    def get(self, request: Request) -> Response:
        return Response(IndexStatusSerializer(index_status()).data)


class IndexRefreshView(APIView):
    @extend_schema(
        operation_id="index_refresh",
        tags=["index"],
        summary="Run one sync pass now",
        description="Returns the summary of the pass; read `GET /api/index/status/` for state.",
        request=None,
        responses={200: RefreshSummarySerializer},
    )
    def post(self, request: Request) -> Response:
        summary = indexer.sync(Path(settings.VAULT_ROOT))
        return Response(RefreshSummarySerializer(refresh_summary(summary)).data)
