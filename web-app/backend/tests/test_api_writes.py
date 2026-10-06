"""POST /api/notes/, /api/notes/status/, /api/captures/ and /api/captures/triage/ (P1-28).

Each test runs against its own copy of the golden vault (the isolated vault root of
`conftest.py`), indexed before the request. File-system state is asserted next to every
response: the writer's files are the truth, the index follows them.
"""

import logging
import os
import shutil
import threading
from pathlib import Path

import pytest
from api_support import GOLDEN, REFERENCE_DATE
from django.db import connection, connections
from django.test import Client

from api.views import writes
from vault import conformance, indexer
from vault.indexer import Indexer
from vault.models import Note
from vault.writer import ConflictError, VaultWriter, content_hash

pytestmark = pytest.mark.django_db

CAPTURE = "00-Inbox/2026-10-08 0915 Buy a spare hinge for the gate.md"
CAPTURE_TEXT = "Buy a spare hinge for the gate"
TASK = "02-Work/Tasks/Check the ladder rungs.md"
DECISION = "05-Knowledge/Decisions/Lantern Festival.md"
ACCEPTED = "05-Knowledge/Decisions/Use warm white bulbs.md"
BROKEN = "02-Work/Tasks/Broken yaml task.md"
ZERO_HASH = "0" * 64


@pytest.fixture
def vault(settings, isolated_vault, pinned_today):
    """The golden vault copied into this test's vault root and indexed."""
    shutil.copytree(GOLDEN / "vault", isolated_vault, dirs_exist_ok=True)
    indexer.sync(isolated_vault)
    return isolated_vault


def snapshot(root: Path) -> dict[str, bytes]:
    """Every file under the vault with its bytes (symlinks are not followed)."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def digest(root: Path, rel: str) -> str:
    return content_hash((root / rel).read_bytes())


def post(client, url, data=None):
    return client.post(url, data or {}, content_type="application/json")


def create(api, **fields):
    return post(api, "/api/notes/", fields)


def capture_note(api, text=CAPTURE_TEXT):
    return post(api, "/api/captures/", {"text": text})


def triage(api, root, **fields):
    body = {"path": CAPTURE, "expected_hash": digest(root, CAPTURE), **fields}
    return post(api, "/api/captures/triage/", body)


def frontmatter_lines(root: Path, rel: str) -> list[str]:
    text = (root / rel).read_text(encoding="utf-8")
    return text.split("---\n")[1].splitlines()


def added(before: dict[str, bytes], after: dict[str, bytes]) -> set[str]:
    return set(after) - set(before)


# --- create -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("note_type", "folder"),
    [
        ("task", "02-Work/Tasks"),
        ("project", "02-Work/Projects"),
        ("decision", "05-Knowledge/Decisions"),
        ("lesson", "05-Knowledge/Lessons"),
    ],
)
def test_create_returns_the_indexed_note_and_the_file_exists(api, vault, note_type, folder):
    response = create(api, type=note_type, title="Fresh idea")
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["path"] == f"{folder}/Fresh idea.md"
    assert body["type"] == note_type and body["title"] == "Fresh idea"
    assert (vault / body["path"]).is_file()
    assert Note.objects.get(path=body["path"]).note_id == body["id"]


def test_create_response_equals_a_later_lookup(api, vault):
    created = create(
        api, type="task", title="Match the lookup", project="harbor-lights", priority="high"
    ).json()
    looked_up = api.get("/api/notes/lookup/", {"path": created["path"]}).json()
    assert {key: looked_up[key] for key in created} == created
    assert created["project"] == "harbor-lights" and created["priority"] == "high"


def test_create_takes_optional_fields(api, vault):
    response = create(
        api,
        type="task",
        title="Everything given",
        project="Harbor Lights",
        priority="low",
        due="2026-11-01",
        status="in-progress",
        body="First line of the body.",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert (body["status"], body["priority"], body["due"]) == ("in-progress", "low", "2026-11-01")
    assert "First line of the body." in (vault / body["path"]).read_text()


def test_same_folder_collision_is_409_and_nothing_changes(api, vault):
    before = snapshot(vault)
    response = create(api, type="task", title="paint the GATE")
    assert response.status_code == 409
    assert snapshot(vault) == before


def test_same_name_in_another_folder_is_allowed(api, vault):
    response = create(api, type="task", title="Harbor Lights")  # a project has this name
    assert response.status_code == 201
    assert response.json()["path"] == "02-Work/Tasks/Harbor Lights.md"


def test_unknown_project_is_422_and_no_file(api, vault):
    before = snapshot(vault)
    response = create(api, type="task", title="Orphan", project="no-such-project")
    assert response.status_code == 422
    assert snapshot(vault) == before
    assert not Note.objects.filter(title="Orphan").exists()


@pytest.mark.parametrize(
    "fields",
    [
        {"type": "capture", "title": "x"},
        {"type": "daily", "title": "2026-10-10"},
        {"type": "task"},
        {"type": "task", "title": "x", "status": "accepted"},
        {"type": "task", "title": "x", "priority": "urgent"},
        {"type": "task", "title": "x", "due": "tomorrow"},
    ],
)
def test_create_rejects_a_bad_request_with_400(api, vault, fields):
    before = snapshot(vault)
    assert create(api, **fields).status_code == 400
    assert snapshot(vault) == before


def test_the_request_body_cannot_carry_a_path_for_create(api, vault):
    response = create(api, type="task", title="Stays put", path="../../escape.md")
    assert response.status_code == 201
    assert response.json()["path"] == "02-Work/Tasks/Stays put.md"
    assert not (vault.parent / "escape.md").exists()
    assert not (vault / "../escape.md").exists()


# --- status -------------------------------------------------------------------------------


def status_request(root, rel=TASK, **fields):
    return {"path": rel, "expected_hash": digest(root, rel), **fields}


def test_status_change_returns_the_detail_and_edits_the_file(api, vault):
    response = post(api, "/api/notes/status/", status_request(vault, status="in-progress"))
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["status"] == "in-progress" and body["content_hash"] == digest(vault, TASK)
    assert "backlinks" in body
    assert "status: in-progress" in frontmatter_lines(vault, TASK)
    assert Note.objects.get(path=TASK).status == "in-progress"


def test_done_appends_evidence_under_notes(api, vault):
    response = post(
        api,
        "/api/notes/status/",
        status_request(vault, status="done", evidence="Checked every rung.\nAll sound."),
    )
    assert response.status_code == 200, response.content
    text = (vault / TASK).read_text()
    assert "## Notes" in text
    assert text.index("## Notes") < text.index("- Checked every rung.")
    assert "- All sound." in text


def test_evidence_with_another_status_is_422_and_the_file_is_unchanged(api, vault):
    before = snapshot(vault)
    response = post(
        api, "/api/notes/status/", status_request(vault, status="blocked", evidence="why")
    )
    assert response.status_code == 422
    assert snapshot(vault) == before


@pytest.mark.parametrize(
    ("rel", "value"),
    [
        (TASK, "accepted"),  # a decision word on a task
        (TASK, "archived"),
        (DECISION, "done"),
        ("05-Knowledge/Lessons/Tag rules.md", "paused"),
        ("02-Work/Projects/Harbor Lights.md", "planned"),
    ],
)
def test_status_outside_the_types_vocabulary_is_422(api, vault, rel, value):
    before = snapshot(vault)
    response = post(api, "/api/notes/status/", status_request(vault, rel, status=value))
    assert response.status_code == 422
    assert snapshot(vault) == before


def test_status_outside_every_vocabulary_is_400(api, vault):
    before = snapshot(vault)
    response = post(api, "/api/notes/status/", status_request(vault, status="someday"))
    assert response.status_code == 400
    assert snapshot(vault) == before


def test_stale_expected_hash_is_409_and_the_file_is_unchanged(api, vault):
    request = status_request(vault, status="done")
    (vault / TASK).write_bytes((vault / TASK).read_bytes() + b"\nObsidian edit\n")
    before = snapshot(vault)
    response = post(api, "/api/notes/status/", request)
    assert response.status_code == 409
    assert snapshot(vault) == before


def test_malformed_frontmatter_is_422_and_the_file_is_unchanged(api, vault):
    before = snapshot(vault)
    response = post(api, "/api/notes/status/", status_request(vault, BROKEN, status="done"))
    assert response.status_code == 422
    assert snapshot(vault) == before


def test_status_of_a_missing_note_is_404(api, vault):
    response = post(
        api,
        "/api/notes/status/",
        {"path": "02-Work/Tasks/Nope.md", "expected_hash": ZERO_HASH, "status": "done"},
    )
    assert response.status_code == 404


@pytest.mark.parametrize("path", ["../outside.md", "/etc/passwd.md", "02-Work/Tasks/x.txt"])
def test_status_path_that_escapes_or_is_not_markdown_is_400(api, vault, path):
    before = snapshot(vault)
    response = post(
        api, "/api/notes/status/", {"path": path, "expected_hash": ZERO_HASH, "status": "done"}
    )
    assert response.status_code == 400
    assert snapshot(vault) == before


def test_a_status_change_on_a_capture_is_422_and_the_file_is_unchanged(api, vault):
    before = snapshot(vault)
    response = post(api, "/api/notes/status/", status_request(vault, CAPTURE, status="dismissed"))
    assert response.status_code == 422
    assert "triage" in response.json()["detail"]
    assert snapshot(vault) == before


def test_a_decision_becoming_accepted_gets_decided_in_the_same_write(api, vault):
    calls = []
    original = VaultWriter._edit

    def counting_edit(self, *args, **kwargs):
        calls.append(args[0])
        return original(self, *args, **kwargs)

    VaultWriter._edit = counting_edit
    try:
        response = post(
            api, "/api/notes/status/", status_request(vault, DECISION, status="accepted")
        )
    finally:
        VaultWriter._edit = original
    assert response.status_code == 200, response.content
    assert calls == [DECISION]  # one file write
    lines = frontmatter_lines(vault, DECISION)
    assert "status: accepted" in lines and f"decided: {REFERENCE_DATE}" in lines
    assert response.json()["decided"] == REFERENCE_DATE


def test_an_already_accepted_decision_keeps_its_decided_date(api, vault):
    before = snapshot(vault)
    response = post(api, "/api/notes/status/", status_request(vault, ACCEPTED, status="accepted"))
    assert response.status_code == 200
    assert snapshot(vault) == before


def test_a_decision_that_is_not_accepted_gets_no_decided_date(api, vault):
    response = post(api, "/api/notes/status/", status_request(vault, DECISION, status="rejected"))
    assert response.status_code == 200
    assert response.json()["decided"] is None


def test_evidence_with_an_accepted_decision_is_422(api, vault):
    before = snapshot(vault)
    response = post(
        api,
        "/api/notes/status/",
        status_request(vault, DECISION, status="accepted", evidence="because"),
    )
    assert response.status_code == 422
    assert snapshot(vault) == before


# --- capture ------------------------------------------------------------------------------


def test_capture_creates_a_capture_note_in_the_inbox(api, vault):
    response = capture_note(api, "Call the electrician about the pier lamps")
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["type"] == "capture" and body["status"] == "inbox"
    assert body["path"].startswith("00-Inbox/") and body["path"].endswith(
        "Call the electrician about the pier lamps.md"
    )
    assert (
        (vault / body["path"])
        .read_text()
        .rstrip()
        .endswith("Call the electrician about the pier lamps")
    )
    assert Note.objects.filter(path=body["path"]).exists()


@pytest.mark.parametrize("data", [{}, {"text": ""}, {"text": "   \n\t "}, {"text": None}])
def test_an_empty_capture_is_400_and_no_file(api, vault, data):
    before = snapshot(vault)
    assert post(api, "/api/captures/", data).status_code == 400
    assert snapshot(vault) == before


def test_a_capture_with_unusable_name_characters_still_files(api, vault):
    response = capture_note(api, 'What about "quotes" and <angles> / slashes?')
    assert response.status_code == 201
    assert "/" not in response.json()["path"].removeprefix("00-Inbox/")


# --- triage -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "classification", "folder"),
    [
        ("task", "task", "02-Work/Tasks"),
        ("task", "problem", "02-Work/Tasks"),
        ("decision", "decision", "05-Knowledge/Decisions"),
        ("lesson", "learning-topic", "05-Knowledge/Lessons"),
        ("lesson", "note", "05-Knowledge/Lessons"),
        ("project", "project", "02-Work/Projects"),
    ],
)
def test_triage_creates_the_target_then_marks_the_capture(
    api, vault, action, classification, folder
):
    before = snapshot(vault)
    response = triage(api, vault, action=action, classification=classification)
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["target"]["path"] == f"{folder}/{CAPTURE_TEXT}.md"
    assert (vault / body["target"]["path"]).is_file()
    assert body["capture"]["path"] == CAPTURE
    assert body["capture"]["status"] == "triaged"
    assert body["capture"]["frontmatter"]["classification"] == classification
    assert body["capture"]["content_hash"] == digest(vault, CAPTURE)
    assert added(before, snapshot(vault)) == {body["target"]["path"]}
    assert Note.objects.filter(path=body["target"]["path"]).exists()


def test_triage_writes_exactly_these_lines_to_the_capture(api, vault):
    original = (vault / CAPTURE).read_text()
    triage(api, vault, action="task", classification="task")
    text = (vault / CAPTURE).read_text()
    head, _, body = text.partition("\n---\n")
    original_head, _, original_body = original.partition("\n---\n")
    assert body == original_body  # the body is untouched
    assert head.splitlines()[: len(original_head.splitlines())] == [
        line if not line.startswith("status:") else "status: triaged"
        for line in original_head.splitlines()
    ]
    assert head.splitlines()[-2:] == [
        "classification: task",
        "triaged_to: '[[Buy a spare hinge for the gate]]'",
    ]


def test_triage_writes_the_target_before_the_capture(api, vault, monkeypatch):
    order = []
    create_original, edit_original = VaultWriter.create, VaultWriter.set_frontmatter
    monkeypatch.setattr(
        VaultWriter,
        "create",
        lambda self, *a, **k: (order.append("target"), create_original(self, *a, **k))[1],
    )
    monkeypatch.setattr(
        VaultWriter,
        "set_frontmatter",
        lambda self, *a, **k: (order.append("capture"), edit_original(self, *a, **k))[1],
    )
    assert triage(api, vault, action="task", classification="task").status_code == 200
    assert order == ["target", "capture"]


def test_triage_title_and_project_are_used(api, vault):
    response = triage(
        api,
        vault,
        action="task",
        classification="task",
        title="Fit a new hinge",
        project="harbor-lights",
    )
    assert response.status_code == 200, response.content
    target = response.json()["target"]
    assert target["path"] == "02-Work/Tasks/Fit a new hinge.md"
    assert target["project"] == "harbor-lights"


def test_triage_link_is_folder_qualified_when_the_name_is_shared(api, vault):
    # A project and a decision are already called "Lantern Festival".
    response = triage(api, vault, action="task", classification="task", title="Lantern Festival")
    assert response.status_code == 200, response.content
    assert "triaged_to: '[[02-Work/Tasks/Lantern Festival]]'" in frontmatter_lines(vault, CAPTURE)


def test_triage_target_collision_is_409_and_nothing_is_written(api, vault):
    before = snapshot(vault)
    response = triage(api, vault, action="task", classification="task", title="Paint the gate")
    assert response.status_code == 409
    assert "created_target" not in response.json()
    assert snapshot(vault) == before


def test_triage_unknown_project_is_422_and_nothing_is_written(api, vault):
    before = snapshot(vault)
    response = triage(api, vault, action="task", classification="task", project="nope")
    assert response.status_code == 422
    assert snapshot(vault) == before


def test_keep_edits_only_the_capture_and_leaves_it_in_the_inbox(api, vault):
    before = snapshot(vault)
    response = triage(api, vault, action="keep", classification="question")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["target"] is None
    assert body["capture"]["status"] == "inbox"
    assert body["capture"]["frontmatter"]["classification"] == "question"
    after = snapshot(vault)
    assert added(before, after) == set()
    assert [p for p in after if after[p] != before[p]] == [CAPTURE]


def test_dismiss_sets_the_status_and_needs_no_classification(api, vault):
    before = snapshot(vault)
    response = triage(api, vault, action="dismiss")
    assert response.status_code == 200, response.content
    assert response.json()["target"] is None
    assert response.json()["capture"]["status"] == "dismissed"
    lines = frontmatter_lines(vault, CAPTURE)
    assert "status: dismissed" in lines
    assert not any(line.startswith(("classification", "triaged_to")) for line in lines)
    assert added(before, snapshot(vault)) == set()


def test_dismiss_writes_a_classification_only_when_one_is_sent(api, vault):
    response = triage(api, vault, action="dismiss", classification="thought")
    assert response.status_code == 200
    assert "classification: thought" in frontmatter_lines(vault, CAPTURE)


@pytest.mark.parametrize("action", ["task", "decision", "lesson", "project", "keep"])
def test_classification_is_required_unless_dismissing(api, vault, action):
    before = snapshot(vault)
    assert triage(api, vault, action=action).status_code == 400
    assert snapshot(vault) == before


@pytest.mark.parametrize(
    "fields",
    [
        {"action": "delete", "classification": "task"},
        {"action": "task", "classification": "banana"},
        {"classification": "task"},
    ],
)
def test_triage_rejects_a_bad_action_or_classification_with_400(api, vault, fields):
    before = snapshot(vault)
    assert triage(api, vault, **fields).status_code == 400
    assert snapshot(vault) == before


@pytest.mark.parametrize("action", ["task", "keep", "dismiss"])
def test_triage_never_deletes_or_moves_the_capture(api, vault, action):
    fields = {"action": action, "classification": "task"}
    assert triage(api, vault, **fields).status_code == 200
    assert (vault / CAPTURE).is_file()
    assert Note.objects.filter(path=CAPTURE).count() == 1
    others = [p for p in os.listdir(vault / "00-Inbox") if p.startswith("2026-10-08 0915")]
    assert others == [CAPTURE.rpartition("/")[2]]


def test_triage_with_a_stale_hash_is_409_and_creates_no_target(api, vault):
    request = {"path": CAPTURE, "expected_hash": digest(vault, CAPTURE)}
    (vault / CAPTURE).write_bytes((vault / CAPTURE).read_bytes() + b"\nmore\n")
    before = snapshot(vault)
    response = post(
        api, "/api/captures/triage/", {**request, "action": "task", "classification": "task"}
    )
    assert response.status_code == 409
    assert "created_target" not in response.json()
    assert snapshot(vault) == before


def test_triage_of_a_note_that_is_not_a_capture_is_422(api, vault):
    before = snapshot(vault)
    response = post(
        api,
        "/api/captures/triage/",
        {
            "path": TASK,
            "expected_hash": digest(vault, TASK),
            "action": "task",
            "classification": "task",
        },
    )
    assert response.status_code == 422
    assert snapshot(vault) == before


def test_triage_of_a_capture_that_is_no_longer_in_the_inbox_is_422(api, vault):
    assert triage(api, vault, action="dismiss").status_code == 200
    before = snapshot(vault)
    response = triage(api, vault, action="task", classification="task")
    assert response.status_code == 422
    assert snapshot(vault) == before


def test_triage_of_a_missing_capture_is_404(api, vault):
    response = post(
        api,
        "/api/captures/triage/",
        {"path": "00-Inbox/Nope.md", "expected_hash": ZERO_HASH, "action": "dismiss"},
    )
    assert response.status_code == 404


def fail_capture_edit(monkeypatch, error):
    """Make only the edit of the capture raise `error`."""
    original = VaultWriter.set_frontmatter

    def failing(self, rel_path, *args, **kwargs):
        if rel_path == CAPTURE:
            raise error
        return original(self, rel_path, *args, **kwargs)

    monkeypatch.setattr(VaultWriter, "set_frontmatter", failing)
    return original


def test_a_failed_capture_edit_reports_the_target_and_a_retry_completes(api, vault, monkeypatch):
    before = snapshot(vault)
    original = fail_capture_edit(monkeypatch, ConflictError("simulated change"))
    response = triage(api, vault, action="task", classification="task")
    assert response.status_code == 409
    created = response.json()["created_target"]
    assert created == f"02-Work/Tasks/{CAPTURE_TEXT}.md"
    assert response.json()["detail"] == "simulated change"
    after = snapshot(vault)
    assert added(before, after) == {created}
    assert after[CAPTURE] == before[CAPTURE]  # the capture is unchanged
    assert Note.objects.filter(path=created).exists()  # the target on disk is indexed

    monkeypatch.setattr(VaultWriter, "set_frontmatter", original)
    retry = triage(api, vault, action="task", classification="task", existing_target=created)
    assert retry.status_code == 200, retry.content
    assert retry.json()["target"]["path"] == created
    final = snapshot(vault)
    assert added(before, final) == {created}  # no second note
    assert Note.objects.filter(title=CAPTURE_TEXT, type="task").count() == 1
    assert "status: triaged" in frontmatter_lines(vault, CAPTURE)
    assert final[created] == after[created]  # the retry did not touch the target


def test_a_422_capture_edit_failure_also_carries_the_target(api, vault, monkeypatch):
    from vault.writer import ValidationError

    fail_capture_edit(monkeypatch, ValidationError("simulated malformed"))
    response = triage(api, vault, action="lesson", classification="note")
    assert response.status_code == 422
    assert response.json()["created_target"] == f"05-Knowledge/Lessons/{CAPTURE_TEXT}.md"


def test_an_unexpected_capture_edit_failure_carries_the_target_without_its_message(
    api, vault, monkeypatch
):
    fail_capture_edit(monkeypatch, RuntimeError("secret detail"))
    response = triage(api, vault, action="task", classification="task")
    assert response.status_code == 500
    assert response.json()["created_target"] == f"02-Work/Tasks/{CAPTURE_TEXT}.md"
    assert "secret" not in response.content.decode()


@pytest.mark.parametrize(
    "target",
    [
        "../outside.md",
        "02-Work/../../outside.md",
        "/etc/hosts.md",
        "C:/Windows/x.md",
        "02-Work\\Tasks\\x.md",
        "02-Work/Tasks/Paint the gate.txt",
        ".obsidian/core.md",
        ".trash/old.md",
        "02-Work/Linked/Paint the gate.md",  # a symlinked folder, created by the test
    ],
)
def test_existing_target_is_confined_before_anything_is_read_or_written(
    api, vault, monkeypatch, target
):
    os.symlink(vault / "02-Work/Tasks", vault / "02-Work/Linked")
    before = snapshot(vault)
    calls = []
    original = Indexer.index_single_file

    def watching(self, root, rel):
        calls.append(rel)
        return original(self, root, rel)

    monkeypatch.setattr(Indexer, "index_single_file", watching)
    response = triage(api, vault, action="task", classification="task", existing_target=target)
    assert response.status_code == 400, response.content
    assert calls == []  # neither the capture nor the target was read or indexed
    assert snapshot(vault) == before


@pytest.mark.parametrize(
    ("action", "classification", "valid"),
    [
        ("task", "learning-topic", False),
        ("task", "ticket", False),
        ("decision", "task", False),
        ("lesson", "project", False),
        ("project", "note", False),
        ("task", "problem", True),
        ("lesson", "learning-topic", True),
        ("keep", "task", True),  # keep and dismiss take any classification
        ("dismiss", "project", True),
    ],
)
def test_the_classification_must_file_as_the_action(api, vault, action, classification, valid):
    before = snapshot(vault)
    response = triage(api, vault, action=action, classification=classification)
    if valid:
        assert response.status_code == 200, response.content
    else:
        assert response.status_code == 400
        assert action in response.json()["detail"] and classification in response.json()["detail"]
        assert snapshot(vault) == before


def test_a_failure_after_the_target_is_created_still_reports_it(api, vault, monkeypatch):
    before = snapshot(vault)
    original = writes.index
    created = f"02-Work/Tasks/{CAPTURE_TEXT}.md"

    def failing(root, rel):
        if rel == created:
            raise RuntimeError("secret index detail")
        return original(root, rel)

    monkeypatch.setattr(writes, "index", failing)
    response = triage(api, vault, action="task", classification="task")
    assert response.status_code == 500
    assert response.json()["created_target"] == created
    assert "secret" not in response.content.decode()
    after = snapshot(vault)
    assert added(before, after) == {created}
    assert after[CAPTURE] == before[CAPTURE]

    monkeypatch.setattr(writes, "index", original)
    retry = triage(api, vault, action="task", classification="task", existing_target=created)
    assert retry.status_code == 200, retry.content
    assert added(before, snapshot(vault)) == {created}  # no second note
    assert Note.objects.filter(title=CAPTURE_TEXT, type="task").count() == 1


def test_the_capture_cannot_be_its_own_target(api, vault):
    before = snapshot(vault)
    response = triage(api, vault, action="task", classification="task", existing_target=CAPTURE)
    assert response.status_code == 422
    assert snapshot(vault) == before


def test_existing_target_must_be_a_note_of_the_actions_type(api, vault):
    before = snapshot(vault)
    response = triage(
        api, vault, action="decision", classification="decision", existing_target=TASK
    )
    assert response.status_code == 422
    assert snapshot(vault) == before


def test_the_link_counts_notes_on_disk_that_are_not_indexed_yet(api, vault):
    stray = vault / "05-Knowledge/Lessons/Fit a new hinge.md"
    stray.write_text("---\ntype: lesson\nstatus: active\ncreated: 2026-10-09\n---\n")
    assert not Note.objects.filter(path="05-Knowledge/Lessons/Fit a new hinge.md").exists()
    response = triage(api, vault, action="task", classification="task", title="Fit a new hinge")
    assert response.status_code == 200, response.content
    assert "triaged_to: '[[02-Work/Tasks/Fit a new hinge]]'" in frontmatter_lines(vault, CAPTURE)


def test_existing_target_that_is_missing_is_404_and_nothing_is_written(api, vault):
    before = snapshot(vault)
    response = triage(
        api,
        vault,
        action="task",
        classification="task",
        existing_target="02-Work/Tasks/Never created.md",
    )
    assert response.status_code == 404
    assert snapshot(vault) == before


def test_existing_target_is_ignored_for_keep_and_dismiss(api, vault):
    response = triage(api, vault, action="keep", classification="note", existing_target="../x.md")
    assert response.status_code == 200
    assert response.json()["target"] is None


# --- every endpoint -----------------------------------------------------------------------

ENDPOINTS = [
    ("/api/notes/", {"type": "task", "title": "Anon"}),
    ("/api/notes/status/", {"path": TASK, "expected_hash": ZERO_HASH, "status": "done"}),
    ("/api/captures/", {"text": "anon"}),
    (
        "/api/captures/triage/",
        {"path": CAPTURE, "expected_hash": ZERO_HASH, "action": "dismiss"},
    ),
]


@pytest.mark.parametrize(("url", "data"), ENDPOINTS)
def test_anonymous_is_403_and_nothing_is_written(client, vault, url, data):
    before = snapshot(vault)
    assert post(client, url, data).status_code == 403
    assert snapshot(vault) == before


@pytest.mark.parametrize(("url", "data"), ENDPOINTS)
def test_csrf_is_enforced(django_user_model, vault, url, data):
    user = django_user_model.objects.create_user(username="csrf", password="x-not-a-secret-1")
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(user)
    before = snapshot(vault)
    response = post(strict, url, data)
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]
    assert snapshot(vault) == before


@pytest.mark.parametrize("bad", ["", "abc", "A" * 64, "g" * 64, "a" * 63, "a" * 65])
@pytest.mark.parametrize(("url", "data"), [ENDPOINTS[1], ENDPOINTS[3]], ids=["status", "triage"])
def test_expected_hash_must_be_64_hex_digits(api, vault, url, data, bad):
    before = snapshot(vault)
    response = post(api, url, {**data, "expected_hash": bad})
    assert response.status_code == 400
    assert snapshot(vault) == before


@pytest.mark.parametrize(
    ("url", "data"),
    [ENDPOINTS[0], ENDPOINTS[2]],
    ids=["create", "capture"],
)
def test_an_unexpected_writer_exception_is_a_generic_500_with_the_traceback_logged(
    api, vault, monkeypatch, caplog, url, data
):
    def explode(self, *args, **kwargs):
        raise RuntimeError("secret /internal/path detail")

    monkeypatch.setattr(VaultWriter, "create", explode)
    with caplog.at_level(logging.ERROR, logger="api.views.writes"):
        response = post(api, url, data)
    assert response.status_code == 500
    assert response.json() == {"detail": writes.GENERIC_ERROR}
    assert "secret" not in response.content.decode()
    logged = [r for r in caplog.records if r.exc_info]
    assert logged and "secret /internal/path detail" in str(logged[0].exc_info[1])


def test_a_bare_writer_error_is_generic_too(api, vault, monkeypatch):
    from vault.sanitize import WriterError

    def disk_trouble(self, *args, **kwargs):
        raise WriterError("could not read the vault: [Errno 5] /mnt/vault/secret")

    monkeypatch.setattr(VaultWriter, "create", disk_trouble)
    response = create(api, type="task", title="Disk")
    assert response.status_code == 500
    assert "secret" not in response.content.decode()


def test_a_failed_file_write_indexes_nothing(api, vault, monkeypatch):
    notes = set(Note.objects.values_list("path", flat=True))
    before = snapshot(vault)

    def fail(self, rel, text):
        raise OSError("disk full")

    monkeypatch.setattr(VaultWriter, "_write_new", fail)
    assert create(api, type="task", title="Never lands").status_code == 500
    assert set(Note.objects.values_list("path", flat=True)) == notes
    assert snapshot(vault) == before


def test_an_indexing_failure_rolls_the_index_back(api, vault, monkeypatch):
    notes = set(Note.objects.values_list("path", flat=True))

    def fail(self, root, rel):
        Note.objects.filter(path=CAPTURE).delete()  # a half-finished index write
        raise RuntimeError("index exploded")

    monkeypatch.setattr(Indexer, "index_single_file", fail)
    assert create(api, type="task", title="File lands").status_code == 500
    assert set(Note.objects.values_list("path", flat=True)) == notes


# --- the advisory lock --------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_the_advisory_lock_is_held_while_the_writer_runs(settings, api, vault, monkeypatch):
    held, release, outcome = threading.Event(), threading.Event(), []
    original = VaultWriter.create

    def slow(self, *args, **kwargs):
        held.set()
        release.wait(10)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(VaultWriter, "create", slow)

    def request():
        try:
            outcome.append(create(api, type="task", title="Slow write"))
        finally:
            connections.close_all()

    worker = threading.Thread(target=request)
    worker.start()
    try:
        assert held.wait(10)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", [indexer.LOCK_KEY])
            assert cursor.fetchone()[0] is False  # the write holds the indexer's lock
    finally:
        release.set()
        worker.join(20)
    assert outcome[0].status_code == 201
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", [indexer.LOCK_KEY])
        assert cursor.fetchone()[0] is True  # released once the request finished


# --- acceptance ---------------------------------------------------------------------------


def test_the_vault_still_conforms_after_every_kind_of_write(api, vault, capsys):
    """Drop the golden notes that are deliberately broken, then write through the API."""
    for finding in conformance.check_vault(vault):
        if finding.code.startswith("F"):
            (vault / finding.path).unlink()
    indexer.reindex(vault)
    assert conformance.main([str(vault)]) == 0

    assert (
        create(api, type="decision", title="Pick a ferry", project="harbor-lights").status_code
        == 201
    )
    assert create(api, type="project", title="Lamp Library").status_code == 201
    made = capture_note(api, "Decided to use the blue lamps").json()["path"]
    assert capture_note(api, "Renew the domain").status_code == 201
    assert (
        post(
            api,
            "/api/notes/status/",
            status_request(vault, "05-Knowledge/Decisions/Pick a ferry.md", status="accepted"),
        ).status_code
        == 200
    )
    assert (
        post(
            api,
            "/api/notes/status/",
            status_request(
                vault,
                "02-Work/Tasks/Sort the seed packets.md",
                status="done",
                evidence="Done and checked",
            ),
        ).status_code
        == 200
    )
    for action, classification, rel in [
        ("decision", "decision", made),
        ("task", "task", CAPTURE),
        (
            "keep",
            "question",
            "00-Inbox/2026-10-08 1605 Why do the garden lights flicker after rain.md",
        ),
    ]:
        response = post(
            api,
            "/api/captures/triage/",
            {
                "path": rel,
                "expected_hash": digest(vault, rel),
                "action": action,
                "classification": classification,
            },
        )
        assert response.status_code == 200, response.content
    capsys.readouterr()
    assert conformance.main([str(vault)]) == 0, capsys.readouterr().out
    assert not [f for f in conformance.check_vault(vault) if f.code.startswith("F")]
