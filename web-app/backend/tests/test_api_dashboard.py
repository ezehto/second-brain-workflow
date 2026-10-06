"""GET /api/dashboard/ (P1-26) against the indexed golden vault."""

from datetime import UTC, datetime

import pytest
from api_support import EXPECTED, GOLDEN, MTIMES, by_bytes, freeze_utc, schema_properties, stem

from vault import conventions, indexer
from vault.models import IndexPass

pytestmark = pytest.mark.django_db

TERMINAL = {"done", "cancelled"}
TODAY = "2026-10-09"


def dashboard(api):
    response = api.get("/api/dashboard/")
    assert response.status_code == 200, response.content
    return response.json()


def paths(items):
    return [item["path"] for item in items]


def open_tasks():
    return [p for p, v in EXPECTED.items() if v["type"] == "task" and v["status"] not in TERMINAL]


def due_order(selected):
    return sorted(
        selected,
        key=lambda p: (
            EXPECTED[p]["due"] is None,
            EXPECTED[p]["due"] or "",
            stem(p).lower(),
            by_bytes(p),
        ),
    )


def test_response_keys_match_the_contract(api, golden_index):
    assert set(dashboard(api)) == schema_properties("Dashboard")


def test_task_sections(api, golden_index):
    data = dashboard(api)
    assert data["today"] == TODAY
    assert paths(data["today_tasks"]) == due_order(
        p for p in open_tasks() if EXPECTED[p]["due"] == TODAY
    )
    assert paths(data["today_tasks"]) == [
        "02-Work/Tasks/Inspect the pier lamps.md",
        "02-Work/Tasks/Order replacement bulbs.md",
        "02-Work/Tasks/Review path layout.md",
    ]
    assert paths(data["in_progress"]) == [
        "02-Work/Tasks/Release checklist.md",
        "02-Work/Tasks/Wire the dock lights.md",
        "02-Work/Tasks/Calibrate light sensor.md",  # no due: last
    ]
    assert paths(data["blocked"]) == [
        "02-Work/Tasks/Fix gate latch.md",
        "02-Work/Tasks/Replace fence post.md",
    ]
    assert paths(data["overdue"]) == due_order(
        p for p in open_tasks() if EXPECTED[p]["due"] and EXPECTED[p]["due"] < TODAY
    )
    assert paths(data["overdue"]) == [
        "02-Work/Tasks/Draft onboarding guide.md",
        "02-Work/Tasks/Tidy the toolshed.md",  # an unknown status is still open
        "02-Work/Tasks/Plan lantern rollout.md",
        "02-Work/Tasks/Release checklist.md",
        "02-Work/Tasks/Fix gate latch.md",
    ]


def test_invalid_due_is_in_no_dated_section(api, golden_index):
    data = dashboard(api)
    dated = paths(data["today_tasks"]) + paths(data["overdue"])
    for invalid in ("Label the storage boxes", "Check the ladder rungs"):
        assert f"02-Work/Tasks/{invalid}.md" not in dated


def test_recent_activity_is_the_ten_newest_notes_then_path(api, golden_index):
    expected = sorted(EXPECTED, key=lambda p: (-MTIMES[p].timestamp(), by_bytes(p)))[:10]
    assert paths(dashboard(api)["recent_activity"]) == expected


def test_active_projects_and_inbox_count(api, golden_index):
    data = dashboard(api)
    active = [p for p, v in EXPECTED.items() if v["type"] == "project" and v["status"] == "active"]
    assert paths(data["active_projects"]) == sorted(active, key=by_bytes)
    counts = {p["slug"]: p["open_task_count"] for p in data["active_projects"]}
    assert counts["harbor-lights"] == 5
    assert counts["lantern-festival"] == 0
    assert (
        data["inbox_count"]
        == sum(1 for v in EXPECTED.values() if v["type"] == "capture" and v["status"] == "inbox")
        == 3
    )


def test_index_summary_comes_from_the_last_pass(api, golden_index):
    index = dashboard(api)["index"]
    assert set(index) == schema_properties("IndexSummary")
    assert index["last_pass_at"] is not None and index["last_pass_at"].endswith("+08:00")
    assert index["problem_count"] > 0


def test_index_summary_without_a_pass(api, golden_index):
    stored = IndexPass.objects.get()
    IndexPass.objects.all().delete()
    try:
        assert dashboard(api)["index"]["last_pass_at"] is None
    finally:
        stored.save()


def test_standup_preview_when_there_is_no_note_today(api, golden_index):
    standup = dashboard(api)["standup"]
    assert standup["exists"] is False
    assert list(standup["preview"]) == list(conventions.STANDUP_HEADINGS)


def test_standup_is_the_touched_daily_note_of_today(api, golden_index, settings, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_TODAY", "2026-10-07")
    settings.VAULT_ROOT = str(golden_index)
    standup = dashboard(api)["standup"]
    assert standup["exists"] is True
    assert standup["untouched"] is False
    assert standup["note"]["path"] == "01-Daily/2026/2026-10-07.md"
    assert set(standup["note"]) == schema_properties("NoteDetail")


def test_standup_reports_an_untouched_note(api, golden_index, settings):
    settings.VAULT_ROOT = str(golden_index)
    target = golden_index / "01-Daily/2026/2026-10-09.md"
    source = GOLDEN / "expected/carry-forward/untouched-note/input.md"
    target.write_bytes(source.read_bytes())
    try:
        indexer.sync(golden_index)
        standup = dashboard(api)["standup"]
        assert standup["exists"] is True and standup["untouched"] is True
    finally:
        target.unlink()


def test_today_and_overdue_follow_the_manila_date(api, golden_index, monkeypatch):
    due_today = [
        "02-Work/Tasks/Inspect the pier lamps.md",
        "02-Work/Tasks/Order replacement bulbs.md",
        "02-Work/Tasks/Review path layout.md",
    ]
    freeze_utc(monkeypatch, datetime(2026, 10, 9, 15, 59, tzinfo=UTC))  # 23:59 on 10-09 Manila
    before = dashboard(api)
    assert before["today"] == "2026-10-09"
    assert paths(before["today_tasks"]) == due_today
    assert not set(due_today) & set(paths(before["overdue"]))

    freeze_utc(monkeypatch, datetime(2026, 10, 9, 16, 1, tzinfo=UTC))  # 00:01 on 10-10 Manila
    after = dashboard(api)
    assert after["today"] == "2026-10-10"
    assert after["today_tasks"] == []
    assert set(due_today) <= set(paths(after["overdue"]))
    assert after["standup"]["exists"] is False


def test_query_count_is_bounded(api, golden_index, settings, django_assert_max_num_queries):
    settings.VAULT_ROOT = str(golden_index)
    # session, user, open tasks + tags, project notes, recent + tags, inbox count, standup
    # (absent: the 3 of the carry-forward preview), index pass and the index
    # problem count
    with django_assert_max_num_queries(15):
        assert api.get("/api/dashboard/").status_code == 200


def test_query_count_with_a_standup_note(
    api, golden_index, settings, monkeypatch, django_assert_max_num_queries
):
    monkeypatch.setenv("SECOND_BRAIN_TODAY", "2026-10-07")
    settings.VAULT_ROOT = str(golden_index)
    with django_assert_max_num_queries(15):
        assert api.get("/api/dashboard/").status_code == 200


def test_anonymous_is_rejected(client, golden_index):
    assert client.get("/api/dashboard/").status_code == 403
