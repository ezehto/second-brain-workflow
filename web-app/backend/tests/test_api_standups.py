"""GET and POST /api/standups/today/ and POST /api/standups/today/append/ (P1-29).

Each test runs against its own copy of the golden vault, indexed before the request. The
expected notes are the fixture's `expected/carry-forward/*` files; file-system state is asserted
next to every response because the vault's files are the truth.
"""

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from api_support import GOLDEN, REFERENCE_DATE, freeze_utc
from django.test import Client

from vault import carry_forward, conventions, indexer
from vault.models import Note
from vault.writer import VaultWriter, content_hash

pytestmark = pytest.mark.django_db

SCENARIOS = GOLDEN / "expected/carry-forward"
NOTE = "01-Daily/2026/2026-10-09.md"
URL = "/api/standups/today/"
APPEND = "/api/standups/today/append/"
ZERO_HASH = "0" * 64


@pytest.fixture
def vault(settings, isolated_vault, pinned_today):
    """The golden vault copied into this test's vault root and indexed."""
    shutil.copytree(GOLDEN / "vault", isolated_vault, dirs_exist_ok=True)
    indexer.sync(isolated_vault)
    return isolated_vault


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def post(client, url, data=None):
    return client.post(url, data or {}, content_type="application/json")


def place(root: Path, scenario: str, name: str = "input.md") -> Path:
    target = root / NOTE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((SCENARIOS / scenario / name).read_bytes())
    return target


def sections(body: str) -> dict[str, list[str]]:
    """The non-blank lines under each standup heading of a note body."""
    return {
        heading: [line for line in carry_forward.section_lines(body, heading) if line.strip()]
        for heading in conventions.STANDUP_HEADINGS
    }


# --- POST: the golden scenarios ------------------------------------------------------------


def test_new_note_equals_the_golden_bytes(api, vault):
    response = post(api, URL)
    assert response.status_code == 201, response.content
    body = response.json()
    assert (body["created"], body["filled"], body["untouched"]) == (True, False, False)
    assert body["note"]["path"] == NOTE
    text = (vault / NOTE).read_text()
    match = re.fullmatch(
        r"---\ntype: daily\nid: (20261009\d{6})\ncreated: 2026-10-09\ntags: \[\]\n---\n(.*)",
        text,
        re.DOTALL,
    )
    assert match, text
    assert match.group(2) == (SCENARIOS / "new-note/expected-body.md").read_text()
    assert body["note"]["id"] == match.group(1)
    assert Note.objects.get(path=NOTE).content_hash == content_hash(text.encode())


def test_untouched_note_is_filled_to_the_golden_bytes(api, vault):
    target = place(vault, "untouched-note")
    response = post(api, URL)
    assert response.status_code == 200, response.content
    body = response.json()
    assert (body["created"], body["filled"], body["untouched"]) == (False, True, False)
    assert target.read_bytes() == (SCENARIOS / "untouched-note/expected.md").read_bytes()
    assert body["note"]["body"] == Note.objects.get(path=NOTE).body


def test_touched_note_is_returned_unchanged(api, vault):
    target = place(vault, "touched-note")
    before = snapshot(vault)
    response = post(api, URL)
    assert response.status_code == 200
    body = response.json()
    assert (body["created"], body["filled"], body["untouched"]) == (False, False, False)
    assert body["note"]["path"] == NOTE
    assert target.read_bytes() == (SCENARIOS / "touched-note/input.md").read_bytes()
    assert snapshot(vault) == {**before, NOTE: before[NOTE]}


def test_a_second_post_is_a_no_op(api, vault):
    assert post(api, URL).status_code == 201
    first = snapshot(vault)
    again = post(api, URL)
    assert again.status_code == 200
    assert (again.json()["created"], again.json()["filled"]) == (False, False)
    assert snapshot(vault) == first


def test_a_malformed_existing_note_is_left_alone(api, vault):
    target = vault / NOTE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("---\ntype: [daily\n---\n# Standup\n")
    before = snapshot(vault)
    response = post(api, URL)
    assert response.status_code == 200
    assert response.json()["filled"] is False
    assert snapshot(vault) == before


def test_an_untouched_note_with_nothing_to_carry_is_not_rewritten(api, vault):
    place(vault, "untouched-note")
    for task in (vault / "02-Work/Tasks").glob("*.md"):
        task.write_text(re.sub(r"(?m)^status: .*$", "status: done", task.read_text(), count=1))
    for daily in (vault / "01-Daily/2026").glob("2026-10-0[1-8].md"):
        daily.unlink()
    before = snapshot(vault)
    response = post(api, URL)
    assert response.status_code == 200
    assert response.json()["filled"] is False and response.json()["untouched"] is True
    assert snapshot(vault) == before


# --- POST: sync pass first, concurrency -----------------------------------------------------


def test_post_runs_a_sync_pass_first_so_a_task_closed_on_disk_is_not_carried(api, vault):
    task = vault / "02-Work/Tasks/Wire the dock lights.md"
    text = task.read_text()
    assert "status: in-progress" in text
    task.write_text(text.replace("status: in-progress", "status: done"))
    assert Note.objects.get(path="02-Work/Tasks/Wire the dock lights.md").status == "in-progress"
    assert post(api, URL).status_code == 201
    carried = (vault / NOTE).read_text()
    assert "[[Wire the dock lights]]" not in carried.split("## Blockers")[0].split("## Today")[1]
    assert "[[Calibrate light sensor]]" in carried


def test_a_concurrent_edit_during_the_fill_is_a_409_with_no_partial_write(api, vault, monkeypatch):
    target = place(vault, "untouched-note")
    real = VaultWriter._read_bytes
    reads = []

    def edited_meanwhile(path):
        if Path(path).name == target.name:
            reads.append(path)
            if len(reads) == 2:  # the re-hash just before the rename
                target.write_text(target.read_text() + "\n- typed in Obsidian\n")
        return real(path)

    monkeypatch.setattr(VaultWriter, "_read_bytes", staticmethod(edited_meanwhile))
    response = post(api, URL)
    assert response.status_code == 409, response.content
    assert "changed" in response.json()["detail"]
    assert target.read_text().endswith("## Related Tasks / Projects\n\n- typed in Obsidian\n")
    assert "[[Wire the dock lights]]" not in target.read_text()
    assert not list((vault / "01-Daily").rglob("*sbw-tmp*"))  # the writer left no temp file


def test_a_template_with_a_time_placeholder_still_gets_its_carry_forward(api, vault):
    template = vault / "08-System/Templates/daily.md"
    template.write_text(template.read_text().replace("## Done", "Opened at {{time}}\n\n## Done"))
    indexer.sync(vault)
    response = post(api, URL)
    assert response.status_code == 201, response.content
    text = (vault / NOTE).read_text()
    assert re.search(r"Opened at \d\d:\d\d", text)
    assert "- [ ] [[Wire the dock lights]]" in text
    assert not list((vault / "01-Daily").rglob("*sbw-tmp*"))


def test_an_existing_note_over_the_edit_limit_is_treated_as_touched(api, vault):
    target = vault / NOTE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(
        (SCENARIOS / "untouched-note/input.md").read_bytes() + b"x" * (5 * 1024 * 1024)
    )
    before = snapshot(vault)
    response = post(api, URL)
    assert response.status_code == 200, response.content
    assert response.json()["filled"] is False
    assert snapshot(vault) == before


def test_failed_start_leaves_the_index_alone(api, vault, monkeypatch):
    place(vault, "untouched-note")

    def refuse(self, *args, **kwargs):
        raise RuntimeError("secret internals")

    monkeypatch.setattr(VaultWriter, "fill_untouched", refuse)
    response = post(api, URL)
    assert response.status_code == 500
    assert "secret" not in response.content.decode()


# --- GET ----------------------------------------------------------------------------------


def test_get_without_a_note_is_404_with_the_preview(api, vault):
    response = api.get(URL)
    assert response.status_code == 404
    body = response.json()
    assert body["exists"] is False
    expected = json.loads((SCENARIOS / "new-note/scenario.json").read_text())["expected_sections"]
    assert body["preview"] == expected


def test_the_preview_is_what_post_then_writes(api, vault):
    preview = api.get(URL).json()["preview"]
    assert post(api, URL).status_code == 201
    assert sections((vault / NOTE).read_text()) == preview
    assert api.get(URL).status_code == 200


def test_get_an_existing_note_reports_untouched(api, vault):
    place(vault, "untouched-note")
    indexer.sync(vault)
    body = api.get(URL).json()
    assert body["exists"] is True and body["untouched"] is True
    assert body["note"]["path"] == NOTE
    place(vault, "touched-note")
    indexer.sync(vault)
    assert api.get(URL).json()["untouched"] is False


def test_get_changes_nothing(api, vault):
    before = snapshot(vault)
    api.get(URL)
    assert snapshot(vault) == before


def test_the_dashboard_shows_the_same_preview(api, vault):
    assert api.get("/api/dashboard/").json()["standup"]["preview"] == api.get(URL).json()["preview"]


# --- today in Manila -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("moment", "note"),
    [
        (datetime(2026, 10, 9, 15, 59, tzinfo=UTC), "01-Daily/2026/2026-10-09.md"),
        (datetime(2026, 10, 9, 16, 1, tzinfo=UTC), "01-Daily/2026/2026-10-10.md"),
    ],
)
def test_the_note_is_named_for_the_manila_date(api, vault, monkeypatch, moment, note):
    freeze_utc(monkeypatch, moment)
    response = post(api, URL)
    assert response.status_code == 201, response.content
    assert response.json()["note"]["path"] == note
    assert (vault / note).is_file()
    assert api.get(URL).json()["note"]["path"] == note


def test_the_year_folder_follows_the_date(api, vault, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_TODAY", "2027-01-01")
    assert post(api, URL).json()["note"]["path"] == "01-Daily/2027/2027-01-01.md"


# --- append -------------------------------------------------------------------------------


def start(api, vault) -> str:
    assert post(api, URL).status_code == 201
    return content_hash((vault / NOTE).read_bytes())


@pytest.mark.parametrize(
    ("section", "line"),
    [
        ("Today", "- [ ] Call the plumber"),
        ("Follow-ups", "- [ ] Call the plumber"),
        ("Done", "- Call the plumber"),
        ("Blockers", "- Call the plumber"),
        ("Decisions / Updates", "- Call the plumber"),
        ("Related Tasks / Projects", "- Call the plumber"),
    ],
)
def test_append_adds_the_marker_of_the_section(api, vault, section, line):
    expected_hash = start(api, vault)
    response = post(
        api,
        APPEND,
        {"section": section, "text": "Call the plumber", "expected_hash": expected_hash},
    )
    assert response.status_code == 200, response.content
    lines = carry_forward.section_lines((vault / NOTE).read_text(), section)
    assert [x for x in lines if x.strip()][-1] == line
    assert response.json()["section_created"] is False
    assert response.json()["note"]["path"] == NOTE
    assert response.json()["note"]["content_hash"] == content_hash((vault / NOTE).read_bytes())


def test_append_changes_only_that_section_and_keeps_one_blank_line(api, vault):
    expected_hash = start(api, vault)
    before = (vault / NOTE).read_text()
    post(api, APPEND, {"section": "Done", "text": "Shipped it", "expected_hash": expected_hash})
    assert (vault / NOTE).read_text() == before.replace(
        "## Done\n\n## Today", "## Done\n\n- Shipped it\n\n## Today"
    )


def test_append_to_an_empty_section_of_a_blank_template_note(api, vault):
    target = place(vault, "untouched-note")
    indexer.sync(vault)
    response = post(
        api,
        APPEND,
        {
            "section": "Today",
            "text": "one\ntwo",
            "expected_hash": content_hash(target.read_bytes()),
        },
    )
    assert response.status_code == 200
    assert "## Today\n\n- [ ] one\n- [ ] two\n\n## Blockers" in target.read_text()


def test_append_reports_a_section_the_writer_had_to_add(api, vault):
    expected_hash = start(api, vault)
    text = (vault / NOTE).read_text()
    (vault / NOTE).write_text(text.replace("## Decisions / Updates\n\n", ""))
    indexer.sync(vault)
    expected_hash = content_hash((vault / NOTE).read_bytes())
    response = post(
        api,
        APPEND,
        {"section": "Decisions / Updates", "text": "Chose X", "expected_hash": expected_hash},
    )
    assert response.status_code == 200, response.content
    assert response.json()["section_created"] is True
    assert (vault / NOTE).read_text().endswith("## Decisions / Updates\n\n- Chose X\n")


def test_append_with_a_stale_hash_is_409_and_nothing_changes(api, vault):
    start(api, vault)
    before = snapshot(vault)
    response = post(api, APPEND, {"section": "Today", "text": "x", "expected_hash": ZERO_HASH})
    assert response.status_code == 409
    assert snapshot(vault) == before


def test_append_after_an_outside_edit_is_409(api, vault):
    expected_hash = start(api, vault)
    (vault / NOTE).write_text((vault / NOTE).read_text() + "\nhand typed\n")
    response = post(api, APPEND, {"section": "Today", "text": "x", "expected_hash": expected_hash})
    assert response.status_code == 409
    assert (vault / NOTE).read_text().endswith("hand typed\n")


def test_append_without_a_note_today_is_404(api, vault):
    before = snapshot(vault)
    response = post(api, APPEND, {"section": "Today", "text": "x", "expected_hash": ZERO_HASH})
    assert response.status_code == 404
    assert snapshot(vault) == before


@pytest.mark.parametrize(
    "data",
    [
        {"section": "Notes", "text": "x", "expected_hash": ZERO_HASH},
        {"section": "Today", "text": "", "expected_hash": ZERO_HASH},
        {"section": "Today", "expected_hash": ZERO_HASH},
        {"section": "Today", "text": "x"},
        {"section": "Today", "text": "x", "expected_hash": "abc"},
    ],
)
def test_append_validates_the_request(api, vault, data):
    start(api, vault)
    before = snapshot(vault)
    assert post(api, APPEND, data).status_code == 400
    assert snapshot(vault) == before


def test_append_text_the_writer_refuses_is_422(api, vault):
    expected_hash = start(api, vault)
    before = snapshot(vault)
    response = post(
        api,
        APPEND,
        {"section": "Done", "text": "x" * (1024 * 1024 + 1), "expected_hash": expected_hash},
    )
    assert response.status_code == 422
    assert snapshot(vault) == before


def test_append_result_is_indexed(api, vault):
    expected_hash = start(api, vault)
    post(api, APPEND, {"section": "Done", "text": "Shipped", "expected_hash": expected_hash})
    assert "- Shipped" in Note.objects.get(path=NOTE).body
    assert REFERENCE_DATE in NOTE


# --- authentication -------------------------------------------------------------------------

POSTS = [
    (URL, None),
    (APPEND, {"section": "Today", "text": "x", "expected_hash": ZERO_HASH}),
]


@pytest.mark.parametrize(("url", "data"), POSTS)
def test_anonymous_is_403_and_nothing_is_written(client, vault, url, data):
    before = snapshot(vault)
    assert post(client, url, data).status_code == 403
    assert snapshot(vault) == before


def test_anonymous_get_is_403(client, vault):
    assert client.get(URL).status_code == 403


@pytest.mark.parametrize(("url", "data"), POSTS)
def test_csrf_is_enforced(django_user_model, vault, url, data):
    user = django_user_model.objects.create_user(username="csrf", password="x-not-a-secret-1")
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(user)
    before = snapshot(vault)
    response = post(strict, url, data)
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]
    assert snapshot(vault) == before
