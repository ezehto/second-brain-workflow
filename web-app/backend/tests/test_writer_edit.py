"""Tests for the writer's edits of an existing note (plan P1-23): frontmatter, status, append to a
section (2.4) and the untouched daily-note fill (2.2)."""

import json
import os
import re
import shutil
from datetime import date, datetime
from pathlib import Path

import pytest

from vault import conventions
from vault.conventions import STANDUP_HEADINGS
from vault.templating import load_template, render
from vault.writer import (
    ConflictError,
    EditResult,
    PathError,
    ValidationError,
    VaultWriter,
    content_hash,
    is_untouched,
)

BACKEND = Path(__file__).resolve().parents[1]
GOLDEN = BACKEND.parents[1] / "second-brain/fixtures/golden-vault"
GOLDEN_VAULT = GOLDEN / "vault"
CARRY = GOLDEN / "expected/carry-forward"
NOW = datetime(2026, 10, 9, 8, 12, 5)

OBSIDIAN = "02-Work/Tasks/Obsidian formatted properties.md"
COMMENTS = "02-Work/Tasks/Task with unknown keys and comments.md"
NO_NEWLINE = "05-Knowledge/Lessons/No trailing newline lesson.md"
BLANK_TAIL = "05-Knowledge/Lessons/Trailing blank lines lesson.md"
CRLF = "05-Knowledge/Lessons/Windows line endings lesson.md"
BOM = "05-Knowledge/Decisions/Byte order mark decision.md"
DAILY = "01-Daily/2026/2026-10-09.md"


@pytest.fixture
def vault(isolated_vault):
    shutil.copytree(GOLDEN_VAULT, isolated_vault, dirs_exist_ok=True)
    return isolated_vault


@pytest.fixture
def writer(vault):
    return VaultWriter(vault, clock=lambda: NOW)


def raw(vault: Path, rel: str) -> bytes:
    return (vault / rel).read_bytes()


def digest(vault: Path, rel: str) -> str:
    return content_hash(raw(vault, rel))


def put(vault: Path, rel: str, content: str | bytes) -> str:
    """Write a file (no newline translation) and return its hash."""
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content if isinstance(content, bytes) else content.encode("utf-8")
    path.write_bytes(data)
    return content_hash(data)


def files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*")}


def set_status(writer, vault, rel, status, **kwargs) -> EditResult:
    return writer.set_status(rel, status, expected_hash=digest(vault, rel), **kwargs)


# --- Frontmatter edits ---------------------------------------------------------------------------


def test_status_edit_changes_only_the_status_line(writer, vault):
    for rel, old_line, new_line in (
        (OBSIDIAN, b"status: planned\n", b"status: in-progress\n"),
        (
            COMMENTS,
            b"status: planned # still to schedule\n",
            b"status: in-progress # still to schedule\n",
        ),
    ):
        before = raw(vault, rel)
        result = set_status(writer, vault, rel, "in-progress")
        after = raw(vault, rel)
        assert after == before.replace(old_line, new_line)
        assert result == EditResult(rel, content_hash(after))


def test_status_edit_keeps_the_body_byte_for_byte(writer, vault):
    for rel in (OBSIDIAN, COMMENTS, NO_NEWLINE, BLANK_TAIL):
        before = raw(vault, rel)
        body_start = before.index(b"\n---", 3) + 4
        new = "done" if "Tasks" in rel else "archived"
        set_status(writer, vault, rel, new)
        assert raw(vault, rel)[raw(vault, rel).index(b"\n---", 3) :] == before[body_start - 4 :]


def test_crlf_and_bom_are_preserved(writer, vault):
    before = raw(vault, CRLF)
    set_status(writer, vault, CRLF, "archived")
    assert raw(vault, CRLF) == before.replace(b"status: active\r\n", b"status: archived\r\n")
    before = raw(vault, BOM)
    assert before.startswith(b"\xef\xbb\xbf---")
    set_status(writer, vault, BOM, "accepted")
    assert raw(vault, BOM) == before.replace(b"status: proposed\n", b"status: accepted\n")


def test_new_keys_are_added_at_the_end_in_the_files_line_endings(writer, vault):
    before = raw(vault, CRLF)
    writer.set_frontmatter(
        CRLF, {"reviewer": "neighbour", "due": "2026-11-02"}, expected_hash=content_hash(before)
    )
    expected = before.replace(
        b"tags: [windows]\r\n---",
        b"tags: [windows]\r\nreviewer: neighbour\r\ndue: 2026-11-02\r\n---",
    )
    assert raw(vault, CRLF) == expected


def test_values_of_each_kind(writer, vault):
    rel = "02-Work/Tasks/Paint the gate.md"
    writer.set_frontmatter(
        rel,
        {
            "priority": "high",
            "due": date(2026, 12, 1),
            "estimate": 3,
            "flag": True,
            "tags": ["a", "b c"],
        },
        expected_hash=digest(vault, rel),
    )
    text = raw(vault, rel).decode()
    assert "priority: high\n" in text
    assert "due: 2026-12-01\n" in text
    assert "estimate: 3\n" in text
    assert "flag: true\n" in text
    assert "tags:\n  - a\n  - b c\n" in text
    writer.set_frontmatter(rel, {"due": None}, expected_hash=digest(vault, rel))
    assert "due:\n" in raw(vault, rel).decode()


def test_text_that_looks_like_another_type_is_quoted(writer, vault):
    rel = "02-Work/Tasks/Paint the gate.md"
    writer.set_frontmatter(
        rel, {"note": "2026-10-25", "link": "[[X]]"}, expected_hash=digest(vault, rel)
    )
    text = raw(vault, rel).decode()
    assert "note: '2026-10-25'\n" in text
    assert "link: '[[X]]'\n" in text


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"": "x"},
        {"a\nb": "x"},
        {"a: b": "x"},
        {"k": {"nested": 1}},
        {"k": object()},
        {"k": float("nan")},
        {"k": "a\x00b"},
        {"k": "\ud800"},
        {"due": "tomorrow"},
        {"due": "2026-02-30"},
        {"k": datetime(2026, 1, 1, 1)},
    ],
)
def test_unusable_changes_are_rejected_and_nothing_is_written(writer, vault, changes):
    rel = COMMENTS
    before = raw(vault, rel)
    with pytest.raises(ValidationError):
        writer.set_frontmatter(rel, changes, expected_hash=content_hash(before))
    assert raw(vault, rel) == before


def test_a_note_with_an_invalid_date_stays_editable_and_the_value_is_untouched(writer, vault):
    rel = "02-Work/Tasks/Check the ladder rungs.md"
    before = raw(vault, rel)
    set_status(writer, vault, rel, "in-progress")
    assert raw(vault, rel) == before.replace(b"status: planned", b"status: in-progress")


def test_an_empty_frontmatter_block_is_valid_and_gets_the_key(writer, vault):
    rel = "00-Inbox/Empty frontmatter block.md"
    before = raw(vault, rel)
    writer.set_frontmatter(rel, {"reviewer": "x"}, expected_hash=content_hash(before))
    assert raw(vault, rel) == before.replace(b"---\n---\n", b"---\nreviewer: x\n---\n", 1)


def test_an_edit_that_changes_nothing_else_keeps_every_other_golden_note_stable(writer, vault):
    """Setting `priority` on every well-formed fixture note changes only that line."""
    checked = 0
    for path in sorted(GOLDEN_VAULT.rglob("*.md")):
        rel = path.relative_to(GOLDEN_VAULT).as_posix()
        if rel.startswith((".", "08-System")) or "Tasks/" not in rel:
            continue
        before = path.read_bytes()
        try:
            writer.set_frontmatter(rel, {"zz_probe": "x"}, expected_hash=content_hash(before))
        except (ValidationError, PathError):
            continue  # malformed or ignored fixtures are refused, covered elsewhere
        after = raw(vault, rel)
        assert after.replace(b"zz_probe: x\n", b"") == before, rel
        checked += 1
    assert checked >= 15


@pytest.mark.parametrize(
    "rel",
    [
        "02-Work/Tasks/Broken yaml task.md",
        "02-Work/Tasks/Unterminated frontmatter task.md",
        "02-Work/Tasks/Duplicate keys task.md",
        "00-Inbox/Frontmatter that is a list.md",
    ],
)
def test_malformed_frontmatter_is_refused(writer, vault, rel):
    before = raw(vault, rel)
    with pytest.raises(ValidationError):
        writer.set_frontmatter(rel, {"status": "done"}, expected_hash=content_hash(before))
    with pytest.raises(ValidationError):
        writer.append_to_section(rel, "## Notes", "x", expected_hash=content_hash(before))
    assert raw(vault, rel) == before


def test_invalid_utf8_is_refused(writer, vault):
    rel = "00-Inbox/Bad bytes.md"
    data = b"---\ntype: capture\nstatus: inbox\n---\n\nbad \xff byte\n"
    h = put(vault, rel, data)
    with pytest.raises(ValidationError):
        writer.set_frontmatter(rel, {"status": "triaged"}, expected_hash=h)
    assert raw(vault, rel) == data


def test_a_note_without_frontmatter_cannot_have_frontmatter_set(writer, vault):
    rel = "00-Inbox/Loose thoughts without frontmatter.md"
    with pytest.raises(ValidationError):
        writer.set_frontmatter(rel, {"status": "x"}, expected_hash=digest(vault, rel))


# --- Hash checks and atomic publish --------------------------------------------------------------


def test_a_stale_expected_hash_conflicts_and_leaves_the_file_alone(writer, vault):
    before = raw(vault, COMMENTS)
    listing = files(vault)
    for call in (
        lambda: writer.set_status(COMMENTS, "done", expected_hash="0" * 64),
        lambda: writer.append_to_section(COMMENTS, "## Notes", "x", expected_hash="stale"),
        lambda: writer.set_frontmatter(COMMENTS, {"a": 1}, expected_hash=""),
    ):
        with pytest.raises(ConflictError):
            call()
    assert raw(vault, COMMENTS) == before
    assert files(vault) == listing


def test_an_edit_between_the_read_and_the_rename_conflicts(writer, vault, monkeypatch):
    """Obsidian saves the note after the writer read it: the pre-rename re-read catches it."""
    before = raw(vault, COMMENTS)
    listing = files(vault)
    obsidian_version = before + b"typed in Obsidian\n"
    real = VaultWriter._read_bytes
    calls = []

    def read_then_edit(path):
        calls.append(path)
        if len(calls) == 2:  # the re-read right before the rename
            Path(path).write_bytes(obsidian_version)
        return real(path)

    monkeypatch.setattr(VaultWriter, "_read_bytes", staticmethod(read_then_edit))
    with pytest.raises(ConflictError):
        writer.set_status(COMMENTS, "done", expected_hash=content_hash(before))
    assert len(calls) == 2
    assert raw(vault, COMMENTS) == obsidian_version
    assert files(vault) == listing  # the temp file is gone


def test_a_failed_publish_removes_its_temp_file(writer, vault, monkeypatch):
    listing = files(vault)

    def refuse(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(Exception, match="could not edit"):
        set_status(writer, vault, COMMENTS, "done")
    assert files(vault) == listing


def test_a_successful_edit_leaves_no_temp_file(writer, vault):
    listing = files(vault)
    set_status(writer, vault, COMMENTS, "done")
    assert files(vault) == listing


def test_the_result_hash_is_the_hash_of_the_file_on_disk_and_chains(writer, vault):
    first = set_status(writer, vault, COMMENTS, "in-progress")
    assert first.content_hash == digest(vault, COMMENTS)
    second = writer.set_status(COMMENTS, "review", expected_hash=first.content_hash)
    assert second.content_hash == digest(vault, COMMENTS)


@pytest.mark.parametrize(
    "rel",
    [
        "../x.md",
        "/etc/passwd",
        "02-Work/Tasks/Nope.md",
        "02-Work/Tasks/Paint the gate.txt",
        "08-System/Templates/task.md",
        ".trash/Wire the dock lights.md",
    ],
)
def test_targets_are_confined_and_must_exist(writer, rel):
    with pytest.raises(PathError):
        writer.set_status(rel, "done", expected_hash="0" * 64)


def test_a_symlinked_note_is_refused(writer, vault, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("---\ntype: task\nstatus: planned\n---\n")
    link = vault / "02-Work/Tasks/Linked.md"
    link.symlink_to(outside)
    with pytest.raises(PathError):
        writer.set_status(
            "02-Work/Tasks/Linked.md", "done", expected_hash=content_hash(outside.read_bytes())
        )
    assert outside.read_text() == "---\ntype: task\nstatus: planned\n---\n"


def test_the_path_is_matched_in_any_letter_case(writer, vault):
    rel = "02-work/tasks/paint the gate.md"
    set_status(writer, vault, "02-Work/Tasks/Paint the gate.md", "review")
    result = writer.set_status(
        rel, "done", expected_hash=digest(vault, "02-Work/Tasks/Paint the gate.md")
    )
    assert b"status: done" in raw(vault, "02-Work/Tasks/Paint the gate.md")
    assert result.path == "02-Work/Tasks/Paint the gate.md"  # the on-disk spelling


# --- Status --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rel", "status"),
    [
        ("02-Work/Tasks/Paint the gate.md", "cancelled"),
        ("02-Work/Projects/Harbor Lights.md", "paused"),
        ("05-Knowledge/Decisions/Use warm white bulbs.md", "accepted"),
        ("05-Knowledge/Lessons/Tag rules.md", "archived"),
        ("00-Inbox/2026-10-07 1730 Tides seem higher this week.md", "triaged"),
    ],
)
def test_every_status_of_each_type_vocabulary_is_accepted(writer, vault, rel, status):
    set_status(writer, vault, rel, status)
    assert re.search(rf"^status: {status}$", raw(vault, rel).decode(), re.MULTILINE)


@pytest.mark.parametrize(
    ("rel", "status"),
    [
        ("02-Work/Tasks/Paint the gate.md", "active"),
        ("02-Work/Projects/Harbor Lights.md", "in-progress"),
        ("05-Knowledge/Lessons/Tag rules.md", "done"),
        ("02-Work/Tasks/Paint the gate.md", ""),
        ("02-Work/Tasks/Paint the gate.md", "Done"),
        (DAILY, "done"),
        ("00-Inbox/Meeting with unknown type.md", "done"),
        ("00-Inbox/Loose thoughts without frontmatter.md", "done"),
    ],
)
def test_a_status_outside_the_types_vocabulary_is_refused(writer, vault, rel, status):
    if rel == DAILY:
        put(vault, rel, (CARRY / "untouched-note/input.md").read_text())
    before = raw(vault, rel)
    with pytest.raises(ValidationError):
        writer.set_status(rel, status, expected_hash=content_hash(before))
    assert raw(vault, rel) == before


def test_done_with_evidence_appends_it_under_notes(writer, vault):
    rel = "02-Work/Tasks/Paint the gate.md"
    before = raw(vault, rel).decode()
    result = set_status(writer, vault, rel, "done", evidence="Verified on site\nPhoto in the album")
    after = raw(vault, rel).decode()
    assert after == before.replace("status: planned", "status: done").replace(
        "## Notes\n\n## Links", "## Notes\n\n- Verified on site\n- Photo in the album\n\n## Links"
    )
    assert result.section_created is False


def test_done_with_evidence_adds_notes_when_the_heading_is_missing(writer, vault):
    rel = "02-Work/Tasks/Plain.md"
    h = put(vault, rel, "---\ntype: task\nstatus: planned\n---\n\n## Description\n\nText\n")
    result = writer.set_status(rel, "done", expected_hash=h, evidence="All good")
    assert raw(vault, rel).decode() == (
        "---\ntype: task\nstatus: done\n---\n\n## Description\n\nText\n\n## Notes\n\n- All good\n"
    )
    assert result.section_created is True


@pytest.mark.parametrize(
    ("status", "evidence"), [("done", None), ("done", "  \n"), ("review", None), ("review", " ")]
)
def test_evidence_is_only_written_for_done_with_text(writer, vault, status, evidence):
    rel = "02-Work/Tasks/Paint the gate.md"
    before = raw(vault, rel)
    set_status(writer, vault, rel, status, evidence=evidence)
    assert raw(vault, rel) == before.replace(b"status: planned", f"status: {status}".encode())


def test_evidence_with_a_status_other_than_done_is_refused_before_any_write(writer, vault):
    rel = "02-Work/Tasks/Paint the gate.md"
    before = raw(vault, rel)
    listing = files(vault)
    with pytest.raises(ValidationError, match="done"):
        set_status(writer, vault, rel, "review", evidence="ignored evidence")
    with pytest.raises(ValidationError):
        set_status(writer, vault, rel, "done", evidence=["not text"])
    assert raw(vault, rel) == before
    assert files(vault) == listing


def test_setting_the_status_it_already_has_publishes_nothing(writer, vault):
    rel = "02-Work/Tasks/Paint the gate.md"
    before = raw(vault, rel)
    result = set_status(writer, vault, rel, "planned")
    assert result == EditResult(rel, content_hash(before), False, False)
    assert raw(vault, rel) == before


# --- Append to a section (2.4) -------------------------------------------------------------------

DOC = "---\ntype: lesson\nstatus: active\n---\n"

APPEND_CASES = {
    "nonempty section, one blank before the next heading": (
        DOC + "# T\n\n## A\n\nold\n\n## B\n\nb\n",
        "## A",
        "new",
        DOC + "# T\n\n## A\n\nold\n- new\n\n## B\n\nb\n",
    ),
    "several blanks collapse to one": (
        DOC + "## A\nold\n\n\n\n## B\n",
        "## A",
        "new",
        DOC + "## A\nold\n- new\n\n## B\n",
    ),
    "no blank before the next heading gets one": (
        DOC + "## A\nold\n## B\n",
        "## A",
        "new",
        DOC + "## A\nold\n- new\n\n## B\n",
    ),
    "empty section: one blank below the heading": (
        DOC + "## A\n\n## B\n",
        "## A",
        "new",
        DOC + "## A\n\n- new\n\n## B\n",
    ),
    "empty section without blank lines": (
        DOC + "## A\n## B\n",
        "## A",
        "new",
        DOC + "## A\n\n- new\n\n## B\n",
    ),
    "rule 2: casefold, trailing hashes and spaces": (
        DOC + "## todAY ##  \n\nold\n\n## B\n",
        "## Today",
        "new",
        DOC + "## todAY ##  \n\nold\n- new\n\n## B\n",
    ),
    "rule 2: unicode casefold": (
        DOC + "## STRASSE\n\n## B\n",
        "## Straße",
        "new",
        DOC + "## STRASSE\n\n- new\n\n## B\n",
    ),
    "rule 2: the level must be equal": (
        DOC + "### A\n\nold\n",
        "## A",
        "new",
        DOC + "### A\n\nold\n\n## A\n\n- new\n",
    ),
    "rule 3: the first of several": (
        DOC + "## A\n\nfirst\n\n## B\n\n## A\n\nsecond\n",
        "## A",
        "new",
        DOC + "## A\n\nfirst\n- new\n\n## B\n\n## A\n\nsecond\n",
    ),
    "rule 4: a lower-level heading stays inside the section": (
        DOC + "## A\n\n### Sub\n\nsub text\n\n## B\n",
        "## A",
        "new",
        DOC + "## A\n\n### Sub\n\nsub text\n- new\n\n## B\n",
    ),
    "rule 4: a higher-level heading ends it": (
        DOC + "### A\n\nold\n\n# Top\n\nt\n",
        "### A",
        "new",
        DOC + "### A\n\nold\n- new\n\n# Top\n\nt\n",
    ),
    "rule 4: the same level ends it, a fence-looking line does not": (
        DOC + "## A\n\nold\n\n## B\n",
        "## A",
        "new",
        DOC + "## A\n\nold\n- new\n\n## B\n",
    ),
    "rule 1: headings in a fenced block are skipped": (
        DOC + "```\n## A\nfake\n```\n\n## A\n\nreal\n\n## B\n",
        "## A",
        "new",
        DOC + "```\n## A\nfake\n```\n\n## A\n\nreal\n- new\n\n## B\n",
    ),
    "rule 1: a heading inside a fence does not end the section": (
        DOC + "## A\n\n~~~\n## B\n~~~\n\n## C\n",
        "## A",
        "new",
        DOC + "## A\n\n~~~\n## B\n~~~\n- new\n\n## C\n",
    ),
    "rule 1: an unclosed fence runs to the end": (
        DOC + "## A\n\nold\n\n```\n## B\n",
        "## A",
        "new",
        DOC + "## A\n\nold\n\n```\n## B\n- new\n",
    ),
    "rule 1: the frontmatter is skipped": (
        "---\ntype: lesson\n# A: not a heading\nstatus: active\n---\n\n## B\n",
        "# A: not a heading",
        "new",
        "---\ntype: lesson\n# A: not a heading\nstatus: active\n---\n\n## B\n\n"
        "# A: not a heading\n\n- new\n",
    ),
    "rule 1: setext headings are not recognised": (
        DOC + "A\n---\n\nold\n",
        "## A",
        "new",
        DOC + "A\n---\n\nold\n\n## A\n\n- new\n",
    ),
    "rule 6: a missing heading is added at the end": (
        DOC + "## A\n\nold\n",
        "## Notes",
        "new",
        DOC + "## A\n\nold\n\n## Notes\n\n- new\n",
    ),
    "rule 6: with a level other than two": (
        DOC + "## A\n\nold\n",
        "#### Deep",
        "new",
        DOC + "## A\n\nold\n\n#### Deep\n\n- new\n",
    ),
    "rule 8: last section, no trailing newline": (
        DOC + "## A\n\nold",
        "## A",
        "new",
        DOC + "## A\n\nold\n- new\n",
    ),
    "rule 8: last section, several trailing blanks": (
        DOC + "## A\n\nold\n\n\n\n",
        "## A",
        "new",
        DOC + "## A\n\nold\n- new\n",
    ),
    "rule 8: empty last section, heading is the last line": (
        DOC + "## A\n\nold\n\n## B",
        "## B",
        "new",
        DOC + "## A\n\nold\n\n## B\n\n- new\n",
    ),
    "rule 8: rule 6 with trailing blanks and no newline": (
        DOC + "## A\n\nold\n\n\n",
        "## Notes",
        "new",
        DOC + "## A\n\nold\n\n## Notes\n\n- new\n",
    ),
    "rule 8: rule 6 on a file that ends at the closing fence": (
        "---\ntype: lesson\nstatus: active\n---",
        "## Notes",
        "new",
        "---\ntype: lesson\nstatus: active\n---\n\n## Notes\n\n- new\n",
    ),
    "rule 8: rule 6 at the closing fence, CRLF": (
        "---\r\ntype: lesson\r\nstatus: active\r\n---",
        "## Notes",
        "new",
        "---\r\ntype: lesson\r\nstatus: active\r\n---\r\n\r\n## Notes\r\n\r\n- new\r\n",
    ),
    "rule 8: rule 6 on a file with only frontmatter": (
        DOC,
        "## Notes",
        "new",
        DOC + "\n## Notes\n\n- new\n",
    ),
    "rule 7: CRLF everywhere, including added lines": (
        (DOC + "## A\n\nold\n\n## B\n").replace("\n", "\r\n"),
        "## A",
        "new",
        (DOC + "## A\n\nold\n- new\n\n## B\n").replace("\n", "\r\n"),
    ),
    "rule 7: CRLF, last section without a line ending": (
        (DOC + "## A\n\nold").replace("\n", "\r\n"),
        "## A",
        "new",
        (DOC + "## A\n\nold\n- new\n").replace("\n", "\r\n"),
    ),
    "rule 7: CRLF and rule 6": (
        (DOC + "## A\n\nold\n").replace("\n", "\r\n"),
        "## Notes",
        "new",
        (DOC + "## A\n\nold\n\n## Notes\n\n- new\n").replace("\n", "\r\n"),
    ),
    "rule 7: the first line break decides": (
        "---\ntype: lesson\r\nstatus: active\n---\n## A\nold\n",
        "## A",
        "new",
        "---\ntype: lesson\r\nstatus: active\n---\n## A\nold\n- new\n",
    ),
    "multi-line text, blank lines dropped, CRLF input normalised": (
        DOC + "## A\n\nold\n",
        "## A",
        "one\r\n\r\ntwo\nthree\n",
        DOC + "## A\n\nold\n- one\n- two\n- three\n",
    ),
}


SECTION_CREATED = {
    "rule 2: the level must be equal",
    "rule 1: the frontmatter is skipped",
    "rule 1: setext headings are not recognised",
    "rule 6: a missing heading is added at the end",
    "rule 6: with a level other than two",
    "rule 8: rule 6 with trailing blanks and no newline",
    "rule 8: rule 6 on a file that ends at the closing fence",
    "rule 8: rule 6 at the closing fence, CRLF",
    "rule 8: rule 6 on a file with only frontmatter",
    "rule 7: CRLF and rule 6",
}


@pytest.mark.parametrize("case", list(APPEND_CASES), ids=list(APPEND_CASES))
def test_append_follows_the_rules_of_2_4(writer, vault, case):
    content, heading, text, expected = APPEND_CASES[case]
    rel = "05-Knowledge/Lessons/Probe.md"
    h = put(vault, rel, content)
    result = writer.append_to_section(rel, heading, text, expected_hash=h)
    assert raw(vault, rel).decode() == expected
    assert result.content_hash == digest(vault, rel)
    assert result.section_created == (case in SECTION_CREATED)


def test_append_adds_a_bom_back(writer, vault):
    rel = "05-Knowledge/Lessons/Probe.md"
    h = put(vault, rel, b"\xef\xbb\xbf" + (DOC + "## A\n\nold\n").encode())
    writer.append_to_section(rel, "## A", "new", expected_hash=h)
    assert raw(vault, rel) == b"\xef\xbb\xbf" + (DOC + "## A\n\nold\n- new\n").encode()


def test_rule_8_on_the_fixture_without_a_trailing_newline(writer, vault):
    before = raw(vault, NO_NEWLINE)
    assert not before.endswith(b"\n")
    result = writer.append_to_section(
        NO_NEWLINE, "## Links", "see [[X]]", expected_hash=content_hash(before)
    )
    assert raw(vault, NO_NEWLINE) == before + b"\n\n- see [[X]]\n"
    assert result.section_created is False


def test_rule_8_on_the_fixture_with_trailing_blank_lines(writer, vault):
    before = raw(vault, BLANK_TAIL)
    assert before.endswith(b"## Links\n\n\n\n")
    writer.append_to_section(
        BLANK_TAIL, "## Links", "see [[X]]", expected_hash=content_hash(before)
    )
    assert raw(vault, BLANK_TAIL) == before.rstrip(b"\n") + b"\n\n- see [[X]]\n"


def test_rule_8_does_not_touch_anything_earlier_in_the_file(writer, vault):
    before = raw(vault, NO_NEWLINE)
    writer.append_to_section(NO_NEWLINE, "## Notes", "new", expected_hash=content_hash(before))
    assert raw(vault, NO_NEWLINE).startswith(before)
    assert raw(vault, NO_NEWLINE).endswith(b"\n\n## Notes\n\n- new\n")


def test_a_section_in_the_middle_of_a_fixture(writer, vault):
    before = raw(vault, NO_NEWLINE).decode()
    writer.append_to_section(
        NO_NEWLINE, "## Lesson", "learned", expected_hash=content_hash(before.encode())
    )
    assert raw(vault, NO_NEWLINE).decode() == before.replace(
        "## Lesson\n\n## Apply", "## Lesson\n\n- learned\n\n## Apply"
    )


def test_a_bad_heading_or_text_is_rejected(writer, vault):
    h = digest(vault, COMMENTS)
    for heading in ("Notes", "####### Seven", "##", "##Notes", "", None):
        with pytest.raises(ValidationError):
            writer.append_to_section(COMMENTS, heading, "x", expected_hash=h)
    for text in ("", "  \n\n", None, "a\x00b", "\ud800"):
        with pytest.raises(ValidationError):
            writer.append_to_section(COMMENTS, "## Notes", text, expected_hash=h)
    assert digest(vault, COMMENTS) == h


# --- The marker rule -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("heading", "marker"),
    [
        ("## Done", "- "),
        ("## Today", "- [ ] "),
        ("## Blockers", "- "),
        ("## Decisions / Updates", "- "),
        ("## Follow-ups", "- [ ] "),
        ("## Related Tasks / Projects", "- "),
        ("## TODAY", "- [ ] "),
        ("## Standup extras", "- "),
    ],
)
def test_a_daily_note_marker_follows_the_section(writer, vault, heading, marker):
    h = put(vault, DAILY, (CARRY / "touched-note/input.md").read_text())
    writer.append_to_section(DAILY, heading, "item", expected_hash=h)
    assert f"\n{marker}item\n" in raw(vault, DAILY).decode()


def test_other_notes_always_get_a_plain_bullet(writer, vault):
    rel = "02-Work/Tasks/Paint the gate.md"
    for heading in ("## Today", "## Follow-ups", "## Notes"):
        writer.append_to_section(rel, heading, "item", expected_hash=digest(vault, rel))
    text = raw(vault, rel).decode()
    assert text.count("- item\n") == 3
    assert "[ ] item" not in text


def test_an_explicit_marker_overrides_the_rule(writer, vault):
    h = put(vault, DAILY, (CARRY / "touched-note/input.md").read_text())
    r = writer.append_to_section(DAILY, "## Today", "plain line", expected_hash=h, marker="")
    writer.append_to_section(DAILY, "## Today", "bullet", expected_hash=r.content_hash, marker="- ")
    text = raw(vault, DAILY).decode()
    assert "- [ ] Water the new seedlings\nplain line\n- bullet\n" in text


# --- The untouched predicate (2.2) ---------------------------------------------------------------


def seed_template(vault: Path) -> str:
    return load_template(vault, "daily")


def test_the_fixtures_untouched_note_is_untouched_and_the_touched_one_is_not(vault):
    template = seed_template(vault)
    day = date(2026, 10, 9)
    assert is_untouched((CARRY / "untouched-note/input.md").read_text(), template, day)
    assert not is_untouched((CARRY / "touched-note/input.md").read_text(), template, day)


def test_whitespace_differences_and_a_different_id_do_not_matter(vault):
    template = seed_template(vault)
    day = date(2026, 10, 9)
    rendered = render(template, title="2026-10-09", when=datetime(2026, 10, 9, 23, 59, 59))
    assert is_untouched(rendered, template, day)
    assert is_untouched(rendered.replace("\n", "\r\n"), template, day)
    spaced = rendered.replace("\n## ", "\n \t\n\n##  ").replace("Done", "Done  ")
    assert is_untouched(spaced, template, day)
    assert is_untouched("﻿" + rendered.replace("20261009", "19990101", 1), template, day)


@pytest.mark.parametrize("section", STANDUP_HEADINGS)
def test_any_one_character_edit_in_a_section_makes_the_note_touched(vault, section):
    template = seed_template(vault)
    day = date(2026, 10, 9)
    rendered = render(template, title="2026-10-09", when=datetime(2026, 10, 9))
    assert is_untouched(rendered, template, day)
    typed = rendered.replace(f"## {section}\n", f"## {section}\nx\n")
    assert not is_untouched(typed, template, day)
    renamed = rendered.replace(f"## {section}\n", f"## {section}x\n")
    assert not is_untouched(renamed, template, day)
    deleted = rendered.replace(f"## {section}\n", f"## {section[:-1]}\n")
    assert not is_untouched(deleted, template, day)


def test_the_title_line_and_the_date_matter(vault):
    template = seed_template(vault)
    rendered = render(template, title="2026-10-09", when=datetime(2026, 10, 9))
    assert not is_untouched(rendered, template, date(2026, 10, 10))
    assert not is_untouched(
        rendered.replace("# Standup", "# Standups"), template, date(2026, 10, 9)
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda t: t.replace("type: daily", "type: task"),
        lambda t: t.replace("type: daily\n", ""),
        lambda t: t.replace("\n---\n# Standup", "\n# Standup", 1),
        lambda t: t.replace("tags: []", "tags: ["),
        lambda t: "\n" + t,
    ],
)
def test_a_note_whose_frontmatter_is_not_a_daily_one_is_touched(vault, mutate):
    template = seed_template(vault)
    rendered = render(template, title="2026-10-09", when=datetime(2026, 10, 9))
    assert not is_untouched(mutate(rendered), template, date(2026, 10, 9))


EDITED_TEMPLATE = """---
type: daily
id: {{date:YYYYMMDDHHmmss}}
created: {{date:YYYY-MM-DD}}
tags: []
---
# Standup - {{title}}

## Done

## Today

## Risks

## Decisions / Updates

## Follow-ups

## Meetings

## Related Tasks / Projects
"""


def edit_template(vault: Path) -> str:
    original = seed_template(vault)
    put(vault, "08-System/Templates/daily.md", EDITED_TEMPLATE)
    return original


def test_with_an_edited_template_a_note_from_it_is_untouched_and_one_from_the_original_is_not(
    vault,
):
    original = edit_template(vault)
    edited = seed_template(vault)
    day = date(2026, 10, 9)
    from_edited = render(edited, title="2026-10-09", when=datetime(2026, 10, 9))
    from_original = render(original, title="2026-10-09", when=datetime(2026, 10, 9))
    assert is_untouched(from_edited, edited, day)
    assert not is_untouched(from_original, edited, day)
    assert not is_untouched(from_edited, original, day)


def test_fill_with_an_edited_template_inserts_where_the_headings_are(writer, vault):
    original = edit_template(vault)
    edited = seed_template(vault)
    h = put(vault, DAILY, render(edited, title="2026-10-09", when=datetime(2026, 10, 9, 8, 12, 5)))
    items = {
        "Today": ["- [ ] [[Plan lantern rollout]]", "    - [ ] sub"],
        "Blockers": ["- [[Fix gate latch]]"],  # renamed to Risks in the template: rule 6 re-adds it
        "Follow-ups": ["- [ ] Email the supplier"],
        "Related Tasks / Projects": ["- [[Harbor Lights]]"],
    }
    result = writer.fill_untouched(DAILY, items, expected_hash=h)
    assert result.changed is True
    assert result.section_created is True
    assert raw(vault, DAILY).decode() == (
        "---\ntype: daily\nid: 20261009081205\ncreated: 2026-10-09\ntags: []\n---\n"
        "# Standup - 2026-10-09\n\n## Done\n\n## Today\n\n"
        "- [ ] [[Plan lantern rollout]]\n    - [ ] sub\n\n"
        "## Risks\n\n## Decisions / Updates\n\n## Follow-ups\n\n- [ ] Email the supplier\n\n"
        "## Meetings\n\n## Related Tasks / Projects\n\n- [[Harbor Lights]]\n\n"
        "## Blockers\n\n- [[Fix gate latch]]\n"
    )
    # a note made from the original template is touched against the edited one
    h2 = put(vault, DAILY, render(original, title="2026-10-09", when=datetime(2026, 10, 9)))
    before = raw(vault, DAILY)
    result = writer.fill_untouched(DAILY, {"Today": ["- [ ] x"]}, expected_hash=h2)
    assert result.changed is False
    assert raw(vault, DAILY) == before


# --- Fill ----------------------------------------------------------------------------------------


def scenario_items(name: str) -> dict[str, list[str]]:
    scenario = json.loads((CARRY / name / "scenario.json").read_text())
    return {key: lines for key, lines in scenario["expected_sections"].items() if lines}


def test_the_fixtures_untouched_note_is_filled_byte_for_byte(writer, vault):
    h = put(vault, DAILY, (CARRY / "untouched-note/input.md").read_bytes())
    result = writer.fill_untouched(DAILY, scenario_items("untouched-note"), expected_hash=h)
    expected = (CARRY / "untouched-note/expected.md").read_bytes()
    assert raw(vault, DAILY) == expected
    assert result == EditResult(DAILY, content_hash(expected), False, True)


def test_the_fixtures_touched_note_comes_back_unchanged(writer, vault):
    data = (CARRY / "touched-note/input.md").read_bytes()
    h = put(vault, DAILY, data)
    listing = files(vault)
    result = writer.fill_untouched(DAILY, scenario_items("untouched-note"), expected_hash=h)
    assert result == EditResult(DAILY, h, False, False)
    mixed = writer.fill_untouched(
        "01-daily/2026/2026-10-09.MD", scenario_items("untouched-note"), expected_hash=h
    )
    assert mixed == EditResult(DAILY, h, False, False)  # the on-disk spelling
    assert raw(vault, DAILY) == data
    assert files(vault) == listing


def test_a_note_deleted_between_the_read_and_the_stat_is_a_conflict(writer, vault, monkeypatch):
    real = VaultWriter._read_bytes

    def read_then_delete(path):
        data = real(path)
        os.unlink(path)  # Obsidian deletes the note right after the writer read it
        return data

    monkeypatch.setattr(VaultWriter, "_read_bytes", staticmethod(read_then_delete))
    with pytest.raises(ConflictError, match="removed"):
        set_status(writer, vault, TASK, "review")
    monkeypatch.undo()
    assert not any(name.startswith(".") and "sbw-tmp" in name for name in files(vault))


def test_a_filled_note_is_touched_so_a_second_fill_changes_nothing(writer, vault):
    h = put(vault, DAILY, (CARRY / "untouched-note/input.md").read_bytes())
    first = writer.fill_untouched(DAILY, scenario_items("untouched-note"), expected_hash=h)
    second = writer.fill_untouched(
        DAILY, scenario_items("untouched-note"), expected_hash=first.content_hash
    )
    assert second.changed is False
    assert raw(vault, DAILY) == (CARRY / "untouched-note/expected.md").read_bytes()


def test_fill_checks_the_hash_before_judging_untouched(writer, vault):
    put(vault, DAILY, (CARRY / "untouched-note/input.md").read_bytes())
    with pytest.raises(ConflictError):
        writer.fill_untouched(DAILY, {"Today": ["- [ ] x"]}, expected_hash="0" * 64)


def test_fill_re_reads_the_file_before_the_rename(writer, vault, monkeypatch):
    data = (CARRY / "untouched-note/input.md").read_bytes()
    h = put(vault, DAILY, data)
    typed = data.replace(b"## Today\n", b"## Today\n\n- [ ] typed\n")
    real = VaultWriter._read_bytes
    calls = []

    def read_then_edit(path):
        calls.append(path)
        if len(calls) == 2:
            Path(path).write_bytes(typed)
        return real(path)

    monkeypatch.setattr(VaultWriter, "_read_bytes", staticmethod(read_then_edit))
    with pytest.raises(ConflictError):
        writer.fill_untouched(DAILY, scenario_items("untouched-note"), expected_hash=h)
    assert raw(vault, DAILY) == typed


def test_fill_keeps_crlf_and_the_bom(writer, vault):
    data = (CARRY / "untouched-note/input.md").read_bytes()
    crlf = b"\xef\xbb\xbf" + data.replace(b"\n", b"\r\n")
    h = put(vault, DAILY, crlf)
    writer.fill_untouched(DAILY, {"Today": ["- [ ] a"], "Follow-ups": ["- [ ] b"]}, expected_hash=h)
    out = raw(vault, DAILY)
    assert out.startswith(b"\xef\xbb\xbf---\r\n")
    assert b"\n" not in out.replace(b"\r\n", b"")
    assert b"## Today\r\n\r\n- [ ] a\r\n\r\n## Blockers" in out
    assert out.endswith(b"## Follow-ups\r\n\r\n- [ ] b\r\n\r\n## Related Tasks / Projects\r\n")


def test_fill_with_nothing_to_insert_publishes_nothing(writer, vault):
    data = (CARRY / "untouched-note/input.md").read_bytes()
    h = put(vault, DAILY, data)
    result = writer.fill_untouched(DAILY, {"Today": []}, expected_hash=h)
    assert result == EditResult(DAILY, h, False, False)
    assert raw(vault, DAILY) == data


@pytest.mark.parametrize(
    "items",
    [
        {"Nope": ["- [ ] x"]},
        {"Today": "- [ ] x"},
        {"Today": ["a\nb"]},
        {"Today": [""]},
        {"Today": ["   "]},
        {"Today": [None]},
        {"Today": ["a\x00"]},
    ],
)
def test_unusable_items_are_rejected(writer, vault, items):
    data = (CARRY / "untouched-note/input.md").read_bytes()
    h = put(vault, DAILY, data)
    with pytest.raises(ValidationError):
        writer.fill_untouched(DAILY, items, expected_hash=h)
    assert raw(vault, DAILY) == data


@pytest.mark.parametrize("rel", ["01-Daily/2026/Not a date.md", "01-Daily/2026/20261009.md"])
def test_fill_needs_a_daily_note_named_by_its_date(writer, vault, rel):
    h = put(vault, rel, (CARRY / "untouched-note/input.md").read_bytes())
    with pytest.raises(ValidationError):
        writer.fill_untouched(rel, {"Today": ["- [ ] x"]}, expected_hash=h)


def test_fill_refuses_a_malformed_note(writer, vault):
    data = b"---\ntype: daily\ntags: [\n---\n# Standup\n"
    h = put(vault, DAILY, data)
    with pytest.raises(ValidationError):
        writer.fill_untouched(DAILY, {"Today": ["- [ ] x"]}, expected_hash=h)
    assert raw(vault, DAILY) == data


def test_the_writer_module_still_has_no_orm_import():
    import ast

    tree = ast.parse((BACKEND / "vault/writer.py").read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert not {m for m in imported if m.startswith("django.db") or m == "vault.models"}
    assert conventions.TEMPLATES_FOLDER


# --- Review findings: limits, structure, modes ---------------------------------------------------

TASK = "02-Work/Tasks/Fix gate latch.md"


def test_frontmatter_limits(writer, vault):
    h = digest(vault, TASK)
    ok = {"a": "x" * 4096, "b": ["i"] * 256}
    writer.set_frontmatter(TASK, ok, expected_hash=h)
    for changes in (
        {"a": "x" * 4097},
        {"a": "é" * 2049},  # 4098 bytes
        {"a": ["i"] * 257},
        {"a": [["nested"]]},
        {"k" * 65: "v"},
    ):
        with pytest.raises(ValidationError):
            writer.set_frontmatter(TASK, changes, expected_hash=digest(vault, TASK))


def test_the_whole_frontmatter_block_is_limited_to_64_kib(writer, vault):
    h = digest(vault, TASK)
    changes = {f"k{n}": "v" * 4000 for n in range(17)}  # 17 values of 4000 bytes: over 64 KiB
    with pytest.raises(ValidationError, match="exceed"):
        writer.set_frontmatter(TASK, changes, expected_hash=h)
    assert digest(vault, TASK) == h


def test_a_note_with_an_oversized_frontmatter_is_not_edited(writer, vault):
    rel = "00-Inbox/Big frontmatter.md"
    data = "---\ntype: capture\nstatus: inbox\n" + "".join(
        f"k{n}: {'v' * 1000}\n" for n in range(70)
    )
    h = put(vault, rel, data + "---\n\nbody\n")
    with pytest.raises(ValidationError, match="larger"):
        writer.set_status(rel, "triaged", expected_hash=h)


@pytest.mark.parametrize(
    "key",
    ["é", "a:b", "a#b", "-a", "a=b", "<<", "~", "", " a", "a ", "a\tb", "a\u2028b", "a\x85b", 5],
)
def test_frontmatter_keys_are_restricted(writer, vault, key):
    before = raw(vault, TASK)
    with pytest.raises(ValidationError):
        writer.set_frontmatter(TASK, {key: "v"}, expected_hash=content_hash(before))
    assert raw(vault, TASK) == before


@pytest.mark.parametrize("key", ["true", "null", "1", "a b", "a.b-c_d", "K" * 64])
def test_keys_that_look_like_other_types_stay_keys(writer, vault, key):
    writer.set_frontmatter(TASK, {key: "v"}, expected_hash=digest(vault, TASK))
    from vault.parser import parse_note

    note = parse_note(TASK, raw(vault, TASK))
    assert note.parse_error is None
    assert note.frontmatter[key] == "v"


@pytest.mark.parametrize("key", ["type", "id", "created"])
def test_identity_keys_are_not_changed(writer, vault, key):
    before = raw(vault, TASK)
    with pytest.raises(ValidationError, match="identifies"):
        writer.set_frontmatter(TASK, {key: "x"}, expected_hash=content_hash(before))
    assert raw(vault, TASK) == before


@pytest.mark.parametrize(
    "value",
    [
        "a\nb: 1",
        "a\rb",
        "a\x85b: 1",
        "a\u2028b",
        "a\u2029b",
        "a\x1bb",
        "done\nevil: 1",
        ["ok", "no\nway"],
    ],
)
def test_line_breaks_and_controls_in_values_are_refused(writer, vault, value):
    before = raw(vault, TASK)
    with pytest.raises(ValidationError):
        writer.set_frontmatter(TASK, {"note_field": value}, expected_hash=content_hash(before))
    assert raw(vault, TASK) == before


@pytest.mark.parametrize(
    "value",
    ["*a", "&a x", "!!python/object:os.system x", "| x", "> x", "{a: 1}", "[1,2]", "# c", "@x",
     "`x", "x # y", "---", "...", "x: y", "- x", "? x", "yes", "null", "~", "0x1F", "1e3",
     "2026-10-09", "\ufeffx", "x\ty", "'", '"', "=", "é", "!binary AAAA"],
)  # fmt: skip
def test_hostile_text_values_round_trip_as_text_and_add_no_keys(writer, vault, value):
    from vault.parser import parse_note

    before = parse_note(TASK, raw(vault, TASK))
    writer.set_frontmatter(TASK, {"note_field": value}, expected_hash=digest(vault, TASK))
    after = parse_note(TASK, raw(vault, TASK))
    assert after.parse_error is None
    assert after.frontmatter["note_field"] == value
    assert set(after.frontmatter) == set(before.frontmatter) | {"note_field"}


def test_the_date_error_names_the_key(writer, vault):
    with pytest.raises(ValidationError, match="decided"):
        writer.set_frontmatter(TASK, {"decided": "soon"}, expected_hash=digest(vault, TASK))
    with pytest.raises(ValidationError, match="created|identifies"):
        writer.set_frontmatter(TASK, {"created": "soon"}, expected_hash=digest(vault, TASK))


def test_a_note_over_5_mib_is_refused_before_it_is_read(writer, vault):
    rel = "00-Inbox/Huge.md"
    data = b"---\ntype: capture\nstatus: inbox\n---\n\n" + b"x" * (5 * 1024 * 1024)
    h = put(vault, rel, data)
    with pytest.raises(ValidationError, match="not edited"):
        writer.set_status(rel, "triaged", expected_hash=h)
    assert raw(vault, rel) == data


# Headings --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "heading",
    [
        "## X\r## Evil",
        "## X\u2028## Evil",
        "## X\u2029y",
        "## X\x85y",
        "## X\ty",
        "## X\u200by",  # Cf: zero-width space
        "## " + "h" * 201,
        "## X\nY",
    ],
)
def test_headings_with_controls_or_excess_length_are_refused(writer, vault, heading):
    before = raw(vault, TASK)
    with pytest.raises(ValidationError):
        writer.append_to_section(TASK, heading, "t", expected_hash=content_hash(before))
    assert raw(vault, TASK) == before


def test_a_heading_of_200_characters_is_accepted(writer, vault):
    result = writer.append_to_section(
        TASK, "## " + "h" * 200, "t", expected_hash=digest(vault, TASK)
    )
    assert result.section_created is True


# Verbatim lines and markers --------------------------------------------------------------------


@pytest.mark.parametrize("marker", ["* ", "- [x] ", "# ", "\n", "-", None.__class__, 5])
def test_only_the_three_markers_are_allowed(writer, vault, marker):
    before = raw(vault, TASK)
    with pytest.raises(ValidationError, match="marker"):
        writer.append_to_section(
            TASK, "## Notes", "x", expected_hash=content_hash(before), marker=marker
        )
    assert raw(vault, TASK) == before


@pytest.mark.parametrize(
    "line",
    ["## Evil", "# H1", "###### six", "#", "   ## indented", "---", "...", " --- ", "```", "~~~~",
     "> ```", "> ## quoted", "```python"],
)  # fmt: skip
def test_verbatim_lines_that_would_act_as_structure_are_refused(writer, vault, line):
    before = raw(vault, TASK)
    with pytest.raises(ValidationError):
        writer.append_to_section(
            TASK, "## Notes", line, expected_hash=content_hash(before), marker=""
        )
    assert raw(vault, TASK) == before


@pytest.mark.parametrize("line", ["## Evil", "---", "```", "# H"])
def test_fill_items_that_would_act_as_structure_are_refused(writer, vault, line):
    data = (CARRY / "untouched-note/input.md").read_bytes()
    h = put(vault, DAILY, data)
    with pytest.raises(ValidationError):
        writer.fill_untouched(DAILY, {"Today": ["- [ ] ok", line]}, expected_hash=h)
    assert raw(vault, DAILY) == data


def test_verbatim_lines_that_only_look_similar_are_accepted(writer, vault):
    h = digest(vault, TASK)
    writer.append_to_section(
        TASK, "## Notes", "#hardware tag\n- [ ] item\n----\n..x", expected_hash=h, marker=""
    )
    assert "#hardware tag\n- [ ] item\n----\n..x\n" in raw(vault, TASK).decode()


def test_text_with_a_marker_cannot_become_structure(writer, vault):
    """With a marker every line is a list item, so heading-like text is harmless."""
    h = digest(vault, TASK)
    writer.append_to_section(TASK, "## Notes", "## Evil\n---\n```", expected_hash=h)
    text = raw(vault, TASK).decode()
    assert "- ## Evil\n- ---\n- ```\n" in text
    from vault.parser import parse_note

    assert parse_note(TASK, text.encode()).parse_error is None


@pytest.mark.parametrize(
    ("typed", "marker", "written"),
    [
        ("- item", "- ", "- item"),
        ("- [ ] item", "- ", "- item"),
        ("- [x] item", "- ", "- item"),
        ("- [X] item", "- [ ] ", "- [ ] item"),
        ("- item", "- [ ] ", "- [ ] item"),
        ("  - item", "- ", "- item"),
        ("-item", "- ", "- -item"),
        ("- - item", "- ", "- - item"),
        ("- [ ] item", "", "- [ ] item"),  # verbatim keeps what it is given
    ],
)
def test_an_existing_list_marker_is_replaced_not_doubled(writer, vault, typed, marker, written):
    writer.append_to_section(
        TASK, "## Notes", typed, expected_hash=digest(vault, TASK), marker=marker
    )
    assert f"## Notes\n\n{written}\n\n## Links" in raw(vault, TASK).decode()


# Fill order, mode, error text, normalisations ----------------------------------------------------


def test_fill_adds_missing_headings_in_template_order_whatever_the_dict_order(writer, vault):
    h = put(
        vault,
        DAILY,
        "---\ntype: daily\nid: 1\ncreated: 2026-10-09\ntags: []\n---\n# Standup - 2026-10-09\n",
    )
    put(
        vault,
        "08-System/Templates/daily.md",
        "---\ntype: daily\nid: {{date:YYYYMMDDHHmmss}}\ncreated: {{date:YYYY-MM-DD}}\n"
        "tags: []\n---\n# Standup - {{title}}\n",
    )
    items = {
        "Related Tasks / Projects": ["- [[P]]"],
        "Follow-ups": ["- [ ] f"],
        "Today": ["- [ ] t"],
        "Blockers": ["- [[B]]"],
    }
    writer.fill_untouched(DAILY, items, expected_hash=h)
    text = raw(vault, DAILY).decode()
    order = re.findall(r"^## (.*)$", text, re.MULTILINE)
    assert order == ["Today", "Blockers", "Follow-ups", "Related Tasks / Projects"]


def test_an_edit_keeps_the_notes_file_mode(writer, vault):
    path = vault / TASK
    path.chmod(0o600)
    set_status(writer, vault, TASK, "review")
    assert (path.stat().st_mode & 0o777) == 0o600
    path.chmod(0o640)
    writer.append_to_section(TASK, "## Notes", "x", expected_hash=digest(vault, TASK))
    assert (path.stat().st_mode & 0o777) == 0o640


def test_error_messages_cut_long_input(writer, vault):
    long = "Z" * 5000
    for call in (
        lambda: writer.append_to_section(TASK, long, "x", expected_hash=digest(vault, TASK)),
        lambda: writer.set_status(TASK, long, expected_hash=digest(vault, TASK)),
        lambda: writer.set_frontmatter(TASK, {long: "v"}, expected_hash=digest(vault, TASK)),
        lambda: writer.set_frontmatter(TASK, {"due": long}, expected_hash=digest(vault, TASK)),
        lambda: writer.fill_untouched(DAILY, {long: ["x"]}, expected_hash="0" * 64),
        lambda: writer.set_status(long + ".md", "done", expected_hash="0" * 64),
    ):
        with pytest.raises(Exception) as caught:
            call()
        assert len(str(caught.value)) < 400, str(caught.value)[:100]


def test_round_trip_normalises_non_obsidian_shapes_but_keeps_meaning(writer, vault):
    """Documented in the module docstring: byte-stable only for Obsidian-shaped frontmatter."""
    from vault.parser import parse_note

    rel = "02-Work/Tasks/Odd shapes.md"
    src = (
        "---\r\ntype: task\r\nstatus: planned\n"
        "items:\n- a\n- b\n"
        "nothing: ~\n"
        "nil: null\n"
        "flag: True\n"
        "plus: +5\n"
        "flow: [a,b]\n"
        "map: {a: 1,b: 2}\n"
        'accent: "\\u00e9"\n'
        "---\r\n\r\nbody\r\n"
    )
    h = put(vault, rel, src)
    before = parse_note(rel, src.encode())
    writer.set_status(rel, "review", expected_hash=h)
    out = raw(vault, rel).decode()
    head, _, body = out.partition("---\r\n\r\n")
    assert body == "body\r\n"
    assert head == (
        "---\r\ntype: task\r\nstatus: review\r\n"
        "items:\r\n  - a\r\n  - b\r\n"
        "nothing:\r\n"
        "nil:\r\n"
        "flag: true\r\n"
        "plus: 5\r\n"
        "flow: [a, b]\r\n"
        "map: {a: 1, b: 2}\r\n"
        'accent: "é"\r\n'
    )
    after = parse_note(rel, out.encode())
    assert after.parse_error is None
    assert after.frontmatter == {**before.frontmatter, "status": "review", "plus": 5}
