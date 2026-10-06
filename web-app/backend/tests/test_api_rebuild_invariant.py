"""API-level rebuild invariant (P1-30, plan section 5).

After `reindex` from an empty index every read endpoint returns the same responses it returned
from the incrementally maintained index, and the user account and its login survive.

Only the two timing fields below are stripped. Everything else is compared as served.
"""

import shutil

import pytest
from api_support import GOLDEN
from django.test import Client

from vault import indexer
from vault.indexer import Indexer
from vault.models import IndexPass, Note, Tag
from vault.writer import content_hash

pytestmark = pytest.mark.django_db

PASSWORD = "x-not-a-secret-1"
CAPTURE_TRIAGED = "00-Inbox/2026-10-08 0915 Buy a spare hinge for the gate.md"
CAPTURE_DISMISSED = "00-Inbox/2026-10-08 1240 Maybe the lanterns could change colour at dusk.md"
STATUS_TASK = "02-Work/Tasks/Check the ladder rungs.md"
EDITED = "02-Work/Tasks/Plan lantern rollout.md"
RENAMED_FROM = "02-Work/Tasks/Inspect the pier lamps.md"
RENAMED_TO = "02-Work/Tasks/Inspect the pier lamps after renaming.md"
SEARCHES = ["lantern", "gate", "warm white bulbs", "harbour", "zzzz-matches-nothing"]
ORDERINGS = ["-modified", "due", "title", "path", "-path"]
FILTERS = [
    {},
    {"type": "task"},
    {"status": "planned"},
    {"has_parse_error": "true"},
    {"overdue": "true"},
]
MISSING_ID = "99999999999999"

# What is stripped, and why: `last_pass_at` is the finish time of the last index pass and
# `duration_ms` its length. `IndexPass` is deliberately kept across `reindex` (plan 2.9), and
# `reindex` is itself a pass, so both differ by design. Nothing else is stripped.
STATUS_TIMING = ("last_pass_at", "duration_ms")
DASHBOARD_TIMING = ("last_pass_at",)


def post(client, url, body=None):
    return client.post(url, body or {}, content_type="application/json")


def digest(root, rel):
    return content_hash((root / rel).read_bytes())


@pytest.fixture
def vault(isolated_vault, pinned_today):
    """The golden vault in this test's vault root, indexed. Removed with `tmp_path`."""
    shutil.copytree(GOLDEN / "vault", isolated_vault, dirs_exist_ok=True)
    indexer.sync(isolated_vault)
    return isolated_vault


def run_sequence(api, root):
    """The scripted API writes and disk edits, ending in one sync pass."""
    for body in (
        {"type": "task", "title": "Rebuild probe task", "project": "harbor-lights"},
        {"type": "decision", "title": "Rebuild probe decision"},
        {"type": "lesson", "title": "Rebuild probe lesson"},
    ):
        assert post(api, "/api/notes/", body).status_code == 201
    for text in ("Rebuild probe capture one", "Rebuild probe capture two"):
        assert post(api, "/api/captures/", {"text": text}).status_code == 201
    triage = {"path": CAPTURE_TRIAGED, "expected_hash": digest(root, CAPTURE_TRIAGED)}
    assert (
        post(
            api, "/api/captures/triage/", {**triage, "action": "task", "classification": "task"}
        ).status_code
        == 200
    )
    dismiss = {"path": CAPTURE_DISMISSED, "expected_hash": digest(root, CAPTURE_DISMISSED)}
    assert post(api, "/api/captures/triage/", {**dismiss, "action": "dismiss"}).status_code == 200
    done = {"path": STATUS_TASK, "expected_hash": digest(root, STATUS_TASK)}
    assert (
        post(
            api, "/api/notes/status/", {**done, "status": "done", "evidence": "Every rung checked."}
        ).status_code
        == 200
    )
    with (root / EDITED).open("a", encoding="utf-8") as handle:
        handle.write("\nA line appended on disk.\n")
    (root / RENAMED_FROM).rename(root / RENAMED_TO)
    indexer.sync(root)


def get(client, url, **params):
    response = client.get(url, params)
    return [response.status_code, response.json()]


def listing(api, **params):
    """Every page of `/api/notes/` for these parameters, in page order."""
    pages, number = [], 1
    while True:
        status, body = get(api, "/api/notes/", page_size=50, page=number, **params)
        pages.append([status, body])
        if status != 200 or not body["next"]:
            return pages
        number += 1


def snapshot(api):
    """Every read endpoint's response (status and JSON), keyed by request."""
    shot = {}
    for ordering in ORDERINGS:
        for index, flt in enumerate(FILTERS):
            shot[f"notes {ordering} filter#{index}"] = listing(api, ordering=ordering, **flt)
    paths = [row["path"] for page in listing(api, ordering="path") for row in page[1]["results"]]
    ids = sorted(
        {
            row["id"]
            for page in listing(api, ordering="path")
            for row in page[1]["results"]
            if row["id"]
        }
    )
    for path in paths:
        shot[f"lookup path {path}"] = get(api, "/api/notes/lookup/", path=path)
    for note_id in [*ids, MISSING_ID]:
        shot[f"lookup id {note_id}"] = get(api, "/api/notes/lookup/", id=note_id)
    shot["projects"] = get(api, "/api/projects/")
    for project in shot["projects"][1]:
        shot[f"project {project['slug']}"] = get(api, f"/api/projects/{project['slug']}/")
    shot["project missing"] = get(api, "/api/projects/no-such-project/")
    shot["dashboard"] = get(api, "/api/dashboard/")
    for query in SEARCHES:
        shot[f"search {query}"] = get(api, "/api/search/", q=query)
    shot["index status"] = get(api, "/api/index/status/")
    return shot


def strip_timing(shot):
    """A copy of the snapshot without the two timing fields named above."""
    clean = {key: value for key, value in shot.items()}
    status = dict(clean["index status"][1])
    index = dict(clean["dashboard"][1]["index"])
    for field in STATUS_TIMING:
        del status[field]
    for field in DASHBOARD_TIMING:
        del index[field]
    clean["index status"] = [clean["index status"][0], status]
    clean["dashboard"] = [clean["dashboard"][0], {**clean["dashboard"][1], "index": index}]
    return clean


def assert_invariant(api, root):
    """Snapshot, `reindex`, snapshot, compare; then the user can still log in."""
    before = snapshot(api)
    assert before["index status"][1]["last_pass_at"] is not None
    assert len(before) > 100  # every note and id was visited, not a stub
    Indexer().reindex(root)
    after = snapshot(api)
    assert after.keys() == before.keys()
    differing = [key for key in before if strip_timing(before)[key] != strip_timing(after)[key]]
    assert differing == []
    assert IndexPass.objects.count() == 1  # the singleton survives; reindex does not truncate it
    fresh = Client()
    login = fresh.post(
        "/api/auth/login/",
        {"username": "tester", "password": PASSWORD},
        content_type="application/json",
    )
    assert login.status_code == 200
    assert fresh.get("/api/auth/me/").status_code == 200


def test_every_read_endpoint_is_identical_after_reindex(api, vault):
    run_sequence(api, vault)
    assert Note.objects.filter(title="Rebuild probe task").exists() and Tag.objects.exists()
    assert_invariant(api, vault)


def test_the_sequence_changed_what_the_snapshot_reads(api, vault):
    """Guards against a vacuous comparison: the writes show up in the first snapshot."""
    before = snapshot(api)
    run_sequence(api, vault)
    after = snapshot(api)
    assert strip_timing(before) != strip_timing(after)
    assert get(api, "/api/notes/lookup/", path=RENAMED_TO)[0] == 200
    assert get(api, "/api/notes/lookup/", path=RENAMED_FROM)[0] == 404
    assert get(api, "/api/notes/lookup/", path=STATUS_TASK)[1]["status"] == "done"
    created = "02-Work/Tasks/Rebuild probe task.md"
    assert get(api, "/api/notes/lookup/", path=created)[0] == 200
    assert f"lookup path {created}" in after
    assert get(api, "/api/notes/lookup/", path=CAPTURE_TRIAGED)[1]["status"] == "triaged"
    assert f"lookup path {CAPTURE_TRIAGED}" in after


def test_the_invariant_holds_with_a_standup_started_and_appended(api, vault):
    run_sequence(api, vault)
    started = post(api, "/api/standups/today/")
    assert started.status_code in (200, 201), started.content
    daily = started.json()["note"]
    appended = post(
        api,
        "/api/standups/today/append/",
        {"section": "Today", "text": "Rebuild probe line", "expected_hash": daily["content_hash"]},
    )
    assert appended.status_code == 200, appended.content
    assert_invariant(api, vault)
