"""GET /api/projects/ and /api/projects/{slug}/ (P1-26) against the indexed golden vault."""

import re
import unicodedata

import pytest
from api_support import EXPECTED, MTIMES, by_bytes, schema_properties, stem

pytestmark = pytest.mark.django_db

TERMINAL = {"done", "cancelled"}


def slugify(text: str) -> str:
    """Independent restatement of plan 2.1 for the expectations."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


PROJECTS = sorted((p for p, v in EXPECTED.items() if v["type"] == "project"), key=by_bytes)
SLUG_OWNERS = {}
for _path in PROJECTS:
    SLUG_OWNERS.setdefault(slugify(stem(_path)), []).append(_path)
UNIQUE = {slug: paths[0] for slug, paths in SLUG_OWNERS.items() if len(paths) == 1}


def open_tasks(slug):
    return [
        p
        for p, v in EXPECTED.items()
        if v["type"] == "task" and v["project"] == slug and v["status"] not in TERMINAL
    ]


def test_list_has_every_project_note_by_path(api, golden_index):
    response = api.get("/api/projects/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)  # not paginated
    assert [p["path"] for p in data] == PROJECTS
    assert all(set(p) == schema_properties("ProjectSummary") for p in data)


def test_list_values(api, golden_index):
    by_path = {p["path"]: p for p in api.get("/api/projects/").json()}
    harbor = by_path["02-Work/Projects/Harbor Lights.md"]
    assert harbor["slug"] == "harbor-lights" and harbor["title"] == "Harbor Lights"
    assert harbor["status"] == "active"
    assert harbor["goal"] == "Light the path along the harbor wall."
    assert harbor["open_task_count"] == len(open_tasks("harbor-lights")) == 5
    assert by_path["02-Work/Projects/Quiet Garden.md"]["status"] == "paused"
    assert by_path["02-Work/Projects/Quiet Garden.md"]["open_task_count"] == len(
        open_tasks("quiet-garden")
    )
    assert by_path["02-Work/Projects/Lantern Festival.md"]["open_task_count"] == 0
    assert harbor["modified"].endswith("+08:00")


def test_two_project_notes_with_one_slug_resolve_to_neither(api, golden_index):
    by_path = {p["path"]: p for p in api.get("/api/projects/").json()}
    for path in ("02-Work/Projects/Night Owl.md", "02-Work/Projects/Night-Owl.md"):
        assert by_path[path]["slug"] == "night-owl"
        assert by_path[path]["open_task_count"] == 0  # `Order replacement bulbs` points at neither
    assert api.get("/api/projects/night-owl/").status_code == 404


def test_detail_sections(api, golden_index):
    response = api.get("/api/projects/harbor-lights/")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == schema_properties("ProjectDetail")
    assert data["project"]["slug"] == "harbor-lights"
    assert data["note"]["path"] == "02-Work/Projects/Harbor Lights.md"
    assert data["note"]["backlinks"]  # a full note detail

    tasks = sorted(
        open_tasks("harbor-lights"),
        key=lambda p: (
            EXPECTED[p]["due"] is None,
            EXPECTED[p]["due"] or "",
            stem(p).lower(),
            by_bytes(p),
        ),
    )
    assert [t["path"] for t in data["open_tasks"]] == tasks
    assert "02-Work/Tasks/Test solar panel.md" not in tasks  # done

    decisions = sorted(
        (
            p
            for p, v in EXPECTED.items()
            if v["type"] == "decision" and v["project"] == "harbor-lights"
        ),
        key=lambda p: (-MTIMES[p].timestamp(), by_bytes(p)),
    )
    assert len(decisions) == 2
    assert [d["path"] for d in data["decisions"]] == decisions

    members = [
        p
        for p, v in EXPECTED.items()
        if v["project"] == "harbor-lights" and p != "02-Work/Projects/Harbor Lights.md"
    ]
    recent = sorted(members, key=lambda p: (-MTIMES[p].timestamp(), by_bytes(p)))[:10]
    assert [n["path"] for n in data["recent_notes"]] == recent
    assert len(members) > 10  # the cap is exercised


def test_detail_summary_items_have_the_note_summary_shape(api, golden_index):
    data = api.get("/api/projects/quiet-garden/").json()
    for section in ("open_tasks", "decisions", "recent_notes"):
        assert data[section]
        assert all(set(n) == schema_properties("NoteSummary") for n in data[section])


@pytest.mark.parametrize("slug", ["no-such-project", "lighthouse-tour", "Harbor-Lights"])
def test_unknown_slug_is_404(api, golden_index, slug):
    response = api.get(f"/api/projects/{slug}/")
    assert response.status_code == 404
    assert response.json() == {"detail": "No such project."}


def test_a_project_with_no_tasks_has_empty_sections(api, golden_index):
    data = api.get("/api/projects/lantern-festival/").json()
    assert data["open_tasks"] == []
    assert data["project"]["open_task_count"] == 0
    assert {n["type"] for n in data["decisions"]} == {"decision"}


def test_anonymous_is_rejected(client, golden_index):
    assert client.get("/api/projects/").status_code == 403
    assert client.get("/api/projects/harbor-lights/").status_code == 403


def test_unique_slugs_in_the_fixture_match_the_expectation(api, golden_index):
    listed = {p["slug"] for p in api.get("/api/projects/").json()}
    assert listed == set(SLUG_OWNERS)
    assert set(UNIQUE) == {"harbor-lights", "lantern-festival", "quiet-garden"}


def test_list_query_count_is_bounded(api, golden_index, django_assert_max_num_queries):
    # session, user, project notes, open task slugs
    with django_assert_max_num_queries(4):
        assert api.get("/api/projects/").status_code == 200


def test_detail_query_count_is_bounded(api, golden_index, django_assert_max_num_queries):
    with django_assert_max_num_queries(12):
        assert api.get("/api/projects/harbor-lights/").status_code == 200
