"""GET /api/notes/ and /api/notes/lookup/ (P1-26) against the indexed golden vault."""

import re
import unicodedata
from datetime import UTC, datetime

import pytest
from api_support import EXPECTED, MTIMES, by_bytes, freeze_utc, schema_properties, stem

from api.serializers import NotePagination

pytestmark = pytest.mark.django_db

TERMINAL = {"done", "cancelled"}
TODAY = "2026-10-09"
ALL_PATHS = sorted(EXPECTED, key=by_bytes)


def listing(api, **params):
    """Every path of one unpaginated-sized page, in response order."""
    response = api.get("/api/notes/", {"page_size": 200, **params})
    assert response.status_code == 200, response.content
    return [item["path"] for item in response.json()["results"]]


def expect(predicate, key=by_bytes):
    return sorted((p for p, v in EXPECTED.items() if predicate(p, v)), key=key)


def is_overdue(value, today=TODAY):
    return value["due"] is not None and value["due"] < today and value["status"] not in TERMINAL


# --- filters ------------------------------------------------------------------------------


def test_every_indexed_note_is_listed_by_path_order(api, golden_index):
    assert listing(api, ordering="path") == ALL_PATHS


@pytest.mark.parametrize(
    ("params", "predicate"),
    [
        ({"type": "task"}, lambda p, v: v["type"] == "task"),
        ({"type": "meeting"}, lambda p, v: v["type"] == "meeting"),
        ({"priority": "high"}, lambda p, v: v["priority"] == "high"),
        ({"project": "harbor-lights"}, lambda p, v: v["project"] == "harbor-lights"),
        ({"project": "lighthouse-tour"}, lambda p, v: v["project"] == "lighthouse-tour"),
        ({"tag": "lighting"}, lambda p, v: "lighting" in v["tags"]),
        ({"tag": "#Outdoor"}, lambda p, v: "outdoor" in v["tags"]),
        ({"tag": "eng/backend"}, lambda p, v: "eng/backend" in v["tags"]),
        ({"path_prefix": "02-Work/Tasks/"}, lambda p, v: p.startswith("02-Work/Tasks/")),
        ({"path_prefix": "00-Inbox/20"}, lambda p, v: p.startswith("00-Inbox/20")),
        ({"has_parse_error": "true"}, lambda p, v: v["parse_error"]),
        ({"has_parse_error": "false"}, lambda p, v: not v["parse_error"]),
        (
            {"status": ["planned", "blocked"]},
            lambda p, v: v["status"] in {"planned", "blocked"},
        ),
        ({"status": "someday"}, lambda p, v: v["status"] == "someday"),
        (
            {"type": "task", "status": "planned", "priority": "low"},
            lambda p, v: (v["type"], v["status"], v["priority"]) == ("task", "planned", "low"),
        ),
    ],
)
def test_filter(api, golden_index, params, predicate):
    expected = expect(predicate)
    assert expected, "the fixture must exercise this filter"
    assert listing(api, ordering="path", **params) == expected


def test_repeated_status_is_an_or(api, golden_index):
    response = api.get("/api/notes/?status=planned&status=blocked&ordering=path&page_size=200")
    assert [i["status"] for i in response.json()["results"]] and {
        i["status"] for i in response.json()["results"]
    } == {"planned", "blocked"}


def test_due_filters_are_inclusive_and_skip_notes_without_a_valid_due(api, golden_index):
    assert listing(api, ordering="path", due_before="2026-10-08") == expect(
        lambda p, v: v["due"] is not None and v["due"] <= "2026-10-08"
    )
    assert listing(api, ordering="path", due_after="2026-10-20") == expect(
        lambda p, v: v["due"] is not None and v["due"] >= "2026-10-20"
    )
    both = listing(api, ordering="path", due_after="2026-10-09", due_before="2026-10-09")
    assert both == expect(lambda p, v: v["due"] == TODAY)
    # `Label the storage boxes` (due: next week) and `Check the ladder rungs` (2026-13-01)
    # have an invalid due: no column value, so no date filter matches them.
    everything = listing(api, due_before="2099-12-31")
    for invalid in ("Label the storage boxes", "Check the ladder rungs"):
        assert f"02-Work/Tasks/{invalid}.md" not in everything


def test_overdue_true_excludes_finished_future_and_invalid_due(api, golden_index):
    overdue = listing(api, ordering="path", overdue="true")
    assert overdue == expect(lambda p, v: is_overdue(v))
    assert overdue  # the fixture has several
    for excluded in (
        "02-Work/Tasks/Test solar panel.md",  # done, due today
        "02-Work/Tasks/Label the storage boxes.md",  # invalid due
        "02-Work/Tasks/Check the ladder rungs.md",  # invalid due
        "02-Work/Tasks/Inspect the pier lamps.md",  # due today is not overdue
        "00-Inbox/Task in the wrong folder.md",  # done
    ):
        assert excluded not in overdue


def test_overdue_false_is_the_complement(api, golden_index):
    assert listing(api, ordering="path", overdue="false") == expect(lambda p, v: not is_overdue(v))


def test_filters_combine_with_and(api, golden_index):
    result = listing(api, ordering="path", overdue="true", project="harbor-lights", type="task")
    assert result == expect(
        lambda p, v: is_overdue(v) and v["project"] == "harbor-lights" and v["type"] == "task"
    )
    assert result


@pytest.mark.parametrize(
    "params",
    [
        {"ordering": "created"},
        {"due_before": "next week"},
        {"overdue": "maybe"},
        {"priority": "urgent"},
    ],
)
def test_bad_query_is_400_with_detail(api, golden_index, params):
    response = api.get("/api/notes/", params)
    assert response.status_code == 400
    assert list(response.json()) == ["detail"]


# --- ordering -----------------------------------------------------------------------------


def test_default_ordering_is_newest_first_then_path(api, golden_index):
    expected = sorted(EXPECTED, key=lambda p: (-MTIMES[p].timestamp(), by_bytes(p)))
    assert listing(api) == expected
    assert listing(api, ordering="-modified") == expected


def test_due_ordering_puts_missing_and_invalid_due_last_by_path(api, golden_index):
    def key(path):
        due = EXPECTED[path]["due"]
        return (due is None, due or "", by_bytes(path))

    result = listing(api, ordering="due")
    assert result == sorted(EXPECTED, key=key)
    undated = [p for p in result if EXPECTED[p]["due"] is None]
    assert result[-len(undated) :] == undated == sorted(undated, key=by_bytes)
    assert "02-Work/Tasks/Label the storage boxes.md" in undated


def test_title_ordering_ends_with_path(api, golden_index):
    result = listing(api, ordering="title")
    assert result == sorted(EXPECTED, key=lambda p: (stem(p).lower().encode(), by_bytes(p)))
    # `Release checklist` exists twice: the title tie is broken by path.
    pair = [p for p in result if stem(p) == "Release checklist"]
    assert pair == sorted(pair, key=by_bytes) and len(pair) == 2


# --- pagination and response shape -------------------------------------------------------


def test_pagination_envelope_and_pages(api, golden_index):
    first = api.get("/api/notes/", {"page_size": 10, "ordering": "path"}).json()
    assert set(first) == {"count", "next", "previous", "results"}
    assert first["count"] == len(ALL_PATHS) and first["previous"] is None and first["next"]
    pages = [first["results"]]
    page = 2
    while len(sum(pages, [])) < first["count"]:
        pages.append(
            api.get("/api/notes/", {"page_size": 10, "page": page, "ordering": "path"}).json()[
                "results"
            ]
        )
        page += 1
    assert [i["path"] for i in sum(pages, [])] == ALL_PATHS


def test_a_page_past_the_end_is_404(api, golden_index):
    assert api.get("/api/notes/", {"page": 99}).status_code == 404


def test_page_size_default_and_cap(api, golden_index):
    from datetime import UTC, datetime

    from vault.models import Note

    assert NotePagination.max_page_size == 200
    Note.objects.bulk_create(
        Note(
            path=f"zz-bulk/note {i:03}.md",
            type="note",
            title=f"note {i:03}",
            content_hash="0" * 64,
            file_mtime=datetime(2026, 10, 1, tzinfo=UTC),
            file_size=0,
        )
        for i in range(201)
    )
    total = len(ALL_PATHS) + 201
    assert len(api.get("/api/notes/").json()["results"]) == 50
    capped = api.get("/api/notes/", {"page_size": 500}).json()
    assert capped["count"] == total and len(capped["results"]) == 200
    assert len(api.get("/api/notes/", {"page_size": 201}).json()["results"]) == 200


def test_ordering_by_path_descending_lists_daily_notes_newest_first(api, golden_index):
    response = api.get("/api/notes/", {"type": "daily", "ordering": "-path"})
    assert [n["path"] for n in response.json()["results"]] == [
        "01-Daily/2026/2026-10-07.md",
        "01-Daily/2026/2026-10-05.md",
    ]
    assert listing(api, ordering="-path") == sorted(EXPECTED, key=by_bytes, reverse=True)


def test_status_without_a_value_reports_the_real_message(api, golden_index):
    response = api.get("/api/notes/?status=")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail.startswith("status: ") and "blank" in detail
    assert not detail.rstrip().endswith(": 0")


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("##lighting", []),
        ("#lighting", "lighting"),
        ("Lighting", "lighting"),
        ("eng/", "eng"),
        ("not a tag", []),
        (unicodedata.normalize("NFD", "caf\u00e9"), []),  # no such tag in the fixture
    ],
)
def test_tag_filter_uses_the_parser_normalisation(api, golden_index, tag, expected):
    want = expect(lambda p, v: expected and expected in v["tags"])
    assert listing(api, ordering="path", tag=tag) == want
    if expected:
        assert want


def test_nfd_tag_matches_the_nfc_tag(api, golden_index):
    from vault.models import Note, Tag

    note = Note.objects.get(path="00-Inbox/Empty note.md")
    note.tags.add(Tag.objects.create(name="caf\u00e9"))
    nfd = unicodedata.normalize("NFD", "caf\u00e9")
    assert listing(api, tag=nfd) == ["00-Inbox/Empty note.md"]


def test_overdue_applies_to_every_type(api, golden_index):
    from vault.models import Note

    lesson = "05-Knowledge/Lessons/Release checklist.md"
    Note.objects.filter(path=lesson).update(due="2026-10-01")
    assert lesson in listing(api, overdue="true")
    Note.objects.filter(path=lesson).update(status="done")
    assert lesson not in listing(api, overdue="true")


def test_summary_keys_match_the_contract_and_values_match_the_index(api, golden_index):
    results = api.get("/api/notes/", {"page_size": 200, "ordering": "path"}).json()["results"]
    assert all(set(item) == schema_properties("NoteSummary") for item in results)
    by_path = {item["path"]: item for item in results}
    for path, expected in EXPECTED.items():
        item = by_path[path]
        assert item["title"] == stem(path)
        assert item["type"] == expected["type"]
        assert item["status"] == expected["status"]
        assert item["priority"] == expected["priority"]
        assert item["project"] == expected["project"]
        assert item["due"] == expected["due"]
        assert item["id"] == expected["note_id"]
        assert item["tags"] == expected["tags"]
        assert (item["parse_error"] is not None) == bool(expected["parse_error"])
    assert by_path["02-Work/Tasks/Fix gate latch.md"]["blocked_by"] == "Waiting for hinge delivery"
    assert by_path["02-Work/Tasks/Fix gate latch.md"]["decided"] is None


def test_modified_is_local_time_with_the_manila_offset(api, golden_index):
    item = api.get("/api/notes/", {"ordering": "path", "page_size": 1}).json()["results"][0]
    moment = MTIMES[item["path"]]
    assert item["modified"].endswith("+08:00")
    assert datetime.fromisoformat(item["modified"]) == moment


def test_decided_is_read_from_the_frontmatter(api, golden_index):
    from vault.models import Note

    Note.objects.filter(path="05-Knowledge/Decisions/Use warm white bulbs.md").update(
        frontmatter={"decided": "2026-10-03", "blocked_by": 42}
    )
    Note.objects.filter(path="05-Knowledge/Decisions/Use warm white bulbs 1.md").update(
        frontmatter={"decided": "2026-10-03 later"}
    )
    results = {
        i["path"]: i
        for i in api.get("/api/notes/", {"type": "decision", "page_size": 200}).json()["results"]
    }
    first = results["05-Knowledge/Decisions/Use warm white bulbs.md"]
    assert (first["decided"], first["blocked_by"]) == ("2026-10-03", "42")
    assert results["05-Knowledge/Decisions/Use warm white bulbs 1.md"]["decided"] is None


def test_list_query_count_is_bounded(api, golden_index, django_assert_max_num_queries):
    # session, user, count, page, tags prefetch
    with django_assert_max_num_queries(5):
        assert api.get("/api/notes/", {"page_size": 200}).status_code == 200


def test_anonymous_is_rejected(client, golden_index):
    assert client.get("/api/notes/").status_code == 403
    assert client.get("/api/notes/lookup/?path=x").status_code == 403


# --- today and overdue either side of Manila midnight -----------------------------------


def test_overdue_follows_the_manila_date_across_midnight(api, golden_index, monkeypatch):
    due_today = expect(
        lambda p, v: v["type"] == "task" and v["due"] == TODAY and v["status"] not in TERMINAL
    )
    assert due_today
    freeze_utc(monkeypatch, datetime(2026, 10, 9, 15, 59, tzinfo=UTC))  # 23:59 on 10-09 Manila
    before = listing(api, ordering="path", overdue="true")
    freeze_utc(monkeypatch, datetime(2026, 10, 9, 16, 1, tzinfo=UTC))  # 00:01 on 10-10 Manila
    after = listing(api, ordering="path", overdue="true")
    assert not set(due_today) & set(before)
    assert set(due_today) <= set(after)
    assert set(after) - set(before) == set(due_today)


# --- lookup -------------------------------------------------------------------------------


def lookup(api, **params):
    return api.get("/api/notes/lookup/", params)


def test_lookup_by_path_returns_the_full_note(api, golden_index):
    path = "02-Work/Tasks/Fix gate latch.md"
    response = lookup(api, path=path)
    assert response.status_code == 200
    data = response.json()
    assert set(data) == schema_properties("NoteDetail")
    assert data["path"] == path and data["title"] == "Fix gate latch"
    assert data["frontmatter"]["status"] == "blocked"
    assert data["frontmatter"]["blocked_by"] == "Waiting for hinge delivery"
    assert data["body"].startswith("\n## Description") or data["body"].startswith("## Description")
    assert re.fullmatch(r"[0-9a-f]{64}", data["content_hash"])
    assert data["parse_error"] is None
    assert data["links"] == {
        "Quiet Garden": {"path": "02-Work/Projects/Quiet Garden.md", "state": "resolved"}
    }


def test_lookup_by_id(api, golden_index):
    response = lookup(api, id="20261003093000")
    assert response.status_code == 200
    assert response.json()["path"] == "02-Work/Tasks/Fix gate latch.md"


def test_lookup_duplicate_id_is_409_with_sorted_candidates(api, golden_index):
    response = lookup(api, id="20261003150000")
    assert response.status_code == 409
    body = response.json()
    assert body["candidates"] == sorted(
        [
            "05-Knowledge/Decisions/Use warm white bulbs.md",
            "05-Knowledge/Decisions/Use warm white bulbs 1.md",
        ],
        key=by_bytes,
    )
    assert "detail" in body


@pytest.mark.parametrize(
    "params", [{"path": "02-Work/Tasks/Nope.md"}, {"id": "1"}, {"path": "../../etc/passwd"}]
)
def test_lookup_unknown_is_404(api, golden_index, params):
    assert lookup(api, **params).status_code == 404


@pytest.mark.parametrize("params", [{}, {"path": "a.md", "id": "1"}, {"path": ""}, {"id": ""}])
def test_lookup_needs_exactly_one_key(api, golden_index, params):
    response = lookup(api, **params)
    assert response.status_code == 400
    assert list(response.json()) == ["detail"]


def normal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split()).removesuffix(".md")


def test_links_map_states_for_every_link_form(api, golden_index):
    data = lookup(api, path="05-Knowledge/Lessons/Every link form.md").json()
    links = {normal(spelling): entry for spelling, entry in data["links"].items()}
    # one entry per spelling, and exactly the link set the index expects
    assert set(links) == set(EXPECTED["05-Knowledge/Lessons/Every link form.md"]["links"])
    task, lesson = "02-Work/Tasks/Release checklist.md", "05-Knowledge/Lessons/Release checklist.md"
    assert links["release checklist"] == {"path": task, "state": "ambiguous"}
    assert links["05-knowledge/lessons/release checklist"] == {"path": lesson, "state": "resolved"}
    assert links["harbor lights"] == {
        "path": "02-Work/Projects/Harbor Lights.md",
        "state": "resolved",
    }
    assert links["review path layout"] == {
        "path": "02-Work/Tasks/Review path layout.md",
        "state": "resolved",
    }
    assert links["café lights need weatherproof plugs"]["state"] == "resolved"
    for unresolved in ("moonlight budget", "unresolved from frontmatter", "garden lamp task"):
        assert links[unresolved] == {"path": None, "state": "unresolved"}
    # the spellings are kept as written
    assert (
        "  REVIEW   path layout " not in data["links"] and "REVIEW   path layout" in data["links"]
    )


def test_ambiguous_project_stem_picks_the_shortest_path(api, golden_index):
    data = lookup(api, path="05-Knowledge/Lessons/Festival lighting lesson.md").json()
    assert data["links"]["Lantern Festival"] == {
        "path": "02-Work/Projects/Lantern Festival.md",
        "state": "ambiguous",
    }


def expected_backlinks(path):
    keys = {normal(stem(path))}
    parts = path.removesuffix(".md").split("/")
    keys |= {normal("/".join(parts[i:])) for i in range(len(parts))}
    return keys


def test_backlinks_are_the_notes_that_link_here(api, golden_index):
    path = "02-Work/Projects/Harbor Lights.md"
    keys = expected_backlinks(path)
    expected = [
        {"path": p, "title": stem(p)}
        for p in sorted(EXPECTED, key=by_bytes)
        if p != path and keys & set(EXPECTED[p]["links"])
    ]
    assert len(expected) > 5
    assert lookup(api, path=path).json()["backlinks"] == expected


def test_an_ambiguous_link_is_a_backlink_of_the_note_it_resolves_to_only(api, golden_index):
    task = lookup(api, path="02-Work/Tasks/Release checklist.md").json()["backlinks"]
    lesson = lookup(api, path="05-Knowledge/Lessons/Release checklist.md").json()["backlinks"]
    assert {b["path"] for b in task} == {
        "01-Daily/2026/2026-10-07.md",
        "05-Knowledge/Lessons/Every link form.md",
    }
    assert {b["path"] for b in lesson} == {"05-Knowledge/Lessons/Every link form.md"}


def test_a_note_without_backlinks_has_an_empty_list(api, golden_index):
    assert lookup(api, path="00-Inbox/Empty note.md").json()["backlinks"] == []


def test_lookup_query_count_is_bounded(api, golden_index, django_assert_max_num_queries):
    # session, user, note, tags, all paths, backlink candidates
    with django_assert_max_num_queries(6):
        assert lookup(api, path="02-Work/Projects/Harbor Lights.md").status_code == 200

