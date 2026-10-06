"""Index status and refresh (task P1-27): problems, last pass, test mode, refresh."""

import json
import shutil
import time
from pathlib import Path

import pytest

from api.views.index import ambiguous_targets
from vault import conventions, indexer
from vault.dates import frontmatter_date
from vault.links import resolve_link
from vault.models import IndexPass, Link, Note

GOLDEN = Path(__file__).resolve().parents[3] / "second-brain/fixtures/golden-vault"
STATUS = "/api/index/status/"
REFRESH = "/api/index/refresh/"

pytestmark = pytest.mark.django_db


@pytest.fixture
def vault(isolated_vault):
    shutil.copytree(GOLDEN / "vault", isolated_vault, dirs_exist_ok=True)
    return isolated_vault


@pytest.fixture
def indexed(vault):
    indexer.sync(vault)
    return vault


@pytest.fixture
def api(client, django_user_model):
    client.force_login(django_user_model.objects.create_user(username="tester", password="x"))
    return client


@pytest.fixture
def expected():
    return json.loads((GOLDEN / "expected/index.json").read_text())["notes"]


def paths_of(problems, category):
    return [entry["path"] for entry in problems[category]]


def test_status_and_refresh_require_a_session(client):
    assert client.get(STATUS).status_code == 403
    assert client.post(REFRESH).status_code == 403


def test_status_before_any_pass_has_null_last_pass_and_empty_counts(api):
    body = api.get(STATUS).json()
    assert body["last_pass_at"] is None
    assert body["duration_ms"] is None
    assert body["counts_by_type"] == {}
    assert all(entries == [] for entries in body["problems"].values())


def test_counts_by_type_match_the_index(api, indexed, expected):
    body = api.get(STATUS).json()
    wanted = {}
    for note in expected.values():
        wanted[note["type"]] = wanted.get(note["type"], 0) + 1
    assert body["counts_by_type"] == wanted


def test_status_reports_every_problem_category_of_the_fixture(api, indexed, expected):
    problems = api.get(STATUS).json()["problems"]
    assert set(problems) == {
        "parse_errors",
        "missing_ids",
        "duplicate_ids",
        "ambiguous_links",
        "unknown_project_slugs",
        "duplicate_project_slugs",
        "unknown_statuses",
        "invalid_dates",
    }

    # Categories the fixture's expected index determines exactly.
    assert sorted(paths_of(problems, "parse_errors")) == sorted(
        path for path, note in expected.items() if note["parse_error"]
    )
    assert len(paths_of(problems, "parse_errors")) >= 4  # the four malformed notes
    assert sorted(paths_of(problems, "missing_ids")) == sorted(
        path for path, note in expected.items() if note["note_id"] is None
    )
    ids = [note["note_id"] for note in expected.values() if note["note_id"]]
    shared = {note_id for note_id in ids if ids.count(note_id) > 1}
    assert sorted(paths_of(problems, "duplicate_ids")) == sorted(
        path for path, note in expected.items() if note["note_id"] in shared
    )
    assert sorted(paths_of(problems, "unknown_statuses")) == sorted(
        path
        for path, note in expected.items()
        if note["type"] in conventions.STATUSES
        and note["status"] is not None
        and note["status"] not in conventions.STATUSES[note["type"]]
    )

    # Categories named in the fixture README.
    assert paths_of(problems, "duplicate_project_slugs") == [
        "02-Work/Projects/Night Owl.md",
        "02-Work/Projects/Night-Owl.md",
    ]
    assert paths_of(problems, "unknown_project_slugs") == [
        "02-Work/Tasks/Calibrate light sensor.md"
    ]
    assert paths_of(problems, "unknown_statuses") == ["02-Work/Tasks/Tidy the toolshed.md"]
    assert paths_of(problems, "invalid_dates") == [
        "02-Work/Tasks/Check the ladder rungs.md",
        "02-Work/Tasks/Label the storage boxes.md",
    ]
    assert [(e["path"], e["detail"]) for e in problems["ambiguous_links"]] == [
        ("01-Daily/2026/2026-10-07.md", "[[release checklist]] matches 2 notes"),
        ("05-Knowledge/Lessons/Every link form.md", "[[release checklist]] matches 2 notes"),
        (
            "05-Knowledge/Lessons/Festival lighting lesson.md",
            "[[lantern festival]] matches 2 notes",
        ),
    ]
    for category in problems.values():
        assert all(set(entry) == {"path", "detail"} for entry in category)
        assert [entry["path"] for entry in category] == sorted(entry["path"] for entry in category)


def test_clean_notes_are_not_listed(api, indexed):
    problems = api.get(STATUS).json()["problems"]
    listed = {entry["path"] for entries in problems.values() for entry in entries}
    assert "00-Inbox/2026-10-08 0915 Buy a spare hinge for the gate.md" not in listed


def test_an_invalid_decided_date_is_listed_and_a_valid_one_is_not(api, vault):
    note = (
        "---\ntype: decision\nid: {id}\nstatus: accepted\ncreated: 2026-10-01\n"
        "decided: {decided}\n---\nBody\n"
    )
    (vault / "05-Knowledge/Decisions/Bad decided.md").write_text(
        note.format(id="20260101000001", decided="2026-02-30")
    )
    (vault / "05-Knowledge/Decisions/Good decided.md").write_text(
        note.format(id="20260101000002", decided="2026-02-20")
    )
    indexer.sync(vault)
    listed = paths_of(api.get(STATUS).json()["problems"], "invalid_dates")
    assert "05-Knowledge/Decisions/Bad decided.md" in listed
    assert "05-Knowledge/Decisions/Good decided.md" not in listed


def test_test_mode_is_null_unless_both_variables_are_set(api, monkeypatch):
    monkeypatch.delenv("SECOND_BRAIN_TEST_MODE", raising=False)
    monkeypatch.delenv("SECOND_BRAIN_TODAY", raising=False)
    assert api.get(STATUS).json()["test_mode"] is None
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    assert api.get(STATUS).json()["test_mode"] is None
    monkeypatch.delenv("SECOND_BRAIN_TEST_MODE")
    monkeypatch.setenv("SECOND_BRAIN_TODAY", "2026-10-09")
    assert api.get(STATUS).json()["test_mode"] is None
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    assert api.get(STATUS).json()["test_mode"] == {"today": "2026-10-09"}


def test_status_runs_a_bounded_number_of_queries(api, indexed, django_assert_max_num_queries):
    # session + user (2), last pass, counts, notes, ambiguous targets, their sources,
    # invalid-date candidates: 8 in all; the count does not grow with the vault.
    with django_assert_max_num_queries(8):
        assert api.get(STATUS).status_code == 200


def test_refresh_picks_up_a_changed_file_and_returns_the_summary(api, indexed):
    target = indexed / "02-Work/Tasks/Tidy the toolshed.md"
    text = target.read_text()
    target.write_text(text + "\nAn ultraviolet afterthought.\n")
    response = api.post(REFRESH)
    assert response.status_code == 200
    body = response.json()
    assert body["changed"] == 1
    assert body["added"] == 0
    assert body["removed"] == 0
    assert isinstance(body["duration_ms"], int) and body["duration_ms"] >= 0
    assert set(body) == {
        "duration_ms",
        "scanned",
        "read",
        "added",
        "changed",
        "removed",
        "moved",
        "over_budget",
        "index_parse_errors",
        "index_duplicate_ids",
        "index_missing_ids",
    }
    assert "ultraviolet" in Note.objects.get(path="02-Work/Tasks/Tidy the toolshed.md").body


def test_refresh_reports_new_and_removed_files(api, indexed):
    (indexed / "00-Inbox/Fresh note.md").write_text("Fresh\n")
    (indexed / "00-Inbox/Empty note.md").unlink()
    body = api.post(REFRESH).json()
    assert (body["added"], body["removed"]) == (1, 1)


def test_last_pass_updates_after_refresh(api, indexed):
    first = api.get(STATUS).json()
    assert first["last_pass_at"] is not None
    IndexPass.objects.update(finished_at="2020-01-01T00:00:00Z")
    assert api.get(STATUS).json()["last_pass_at"].startswith("2020-01-01")
    api.post(REFRESH)
    after = api.get(STATUS).json()
    assert after["last_pass_at"] > "2020-01-02"
    assert after["duration_ms"] == IndexPass.objects.get().duration_ms


def test_reindex_keeps_the_last_pass_row(api, vault):
    indexer.sync(vault)
    indexer.reindex(vault)
    assert IndexPass.objects.count() == 1
    assert api.get(STATUS).json()["last_pass_at"] is not None


@pytest.mark.parametrize(
    "decided",
    ["'2026-02-20x'", "'2026-W07-5'", "'2026-02-20 later'", "'2026-02-30'", "'20 Feb 2026'"],
)
def test_decided_values_the_parser_rejects_are_listed(api, vault, decided):
    (vault / "05-Knowledge/Decisions/Odd decided.md").write_text(
        "---\ntype: decision\nid: 20260101000009\nstatus: accepted\ncreated: 2026-10-01\n"
        f"decided: {decided}\n---\nBody\n"
    )
    indexer.sync(vault)
    listed = paths_of(api.get(STATUS).json()["problems"], "invalid_dates")
    assert "05-Knowledge/Decisions/Odd decided.md" in listed


@pytest.mark.parametrize("decided", ["2026-02-20", "2026-02-20T10:00:00Z", "2026-02-20 10:00:00"])
def test_decided_values_the_parser_accepts_are_not_listed(api, vault, decided):
    (vault / "05-Knowledge/Decisions/Fine decided.md").write_text(
        "---\ntype: decision\nid: 20260101000008\nstatus: accepted\ncreated: 2026-10-01\n"
        f"decided: {decided}\n---\nBody\n"
    )
    indexer.sync(vault)
    listed = paths_of(api.get(STATUS).json()["problems"], "invalid_dates")
    assert "05-Knowledge/Decisions/Fine decided.md" not in listed


def test_frontmatter_date_helper():
    from datetime import date

    assert frontmatter_date("2026-02-20") == date(2026, 2, 20)
    assert frontmatter_date("2026-02-20T23:59:00-05:00") == date(2026, 2, 20)
    assert frontmatter_date("2026-02-20 10:00:00") == date(2026, 2, 20)
    for bad in ("2026-02-20x", "2026-W07-5", "2026-02-20 later", "2026-02-30", "", None, 20260220):
        assert frontmatter_date(bad) is None


def test_ambiguity_equals_resolve_link_over_the_golden_vault(indexed):
    note_paths = list(Note.objects.values_list("path", flat=True))
    targets = list(Link.objects.order_by().values_list("target_title", flat=True).distinct())
    wanted = {
        target: len(resolution.matches)
        for target in targets
        if (resolution := resolve_link(target, note_paths)).status == "ambiguous"
    }
    assert wanted  # the fixture has ambiguous links
    assert ambiguous_targets(targets, note_paths) == wanted


def test_ambiguity_matches_resolve_link_for_qualified_targets():
    paths = ["a/Dup.md", "b/Dup.md", "a/b/Dup.md", "c/Solo.md", "Readme.txt"]
    targets = ["dup", "b/dup", "a/dup", "solo", "c/solo", "missing", "a/b/dup"]
    wanted = {
        target: len(resolve_link(target, paths).matches)
        for target in targets
        if resolve_link(target, paths).status == "ambiguous"
    }
    assert ambiguous_targets(targets, paths) == wanted


def test_ambiguity_scales_to_a_thousand_notes_and_two_thousand_targets():
    paths = [f"folder{n % 20}/Note {n}.md" for n in range(1000)] + ["other/Note 5.md"]
    targets = [f"note {n}" for n in range(1000)] + [f"missing {n}" for n in range(1000)]
    started = time.perf_counter()
    found = ambiguous_targets(targets, paths)
    assert time.perf_counter() - started < 0.5
    assert found == {"note 5": 2}
