"""Tests for vault.writer: confinement, atomic create from a template (plan P1-22)."""

import ast
import errno
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import pytest

from vault import conformance, conventions
from vault import writer as writer_module
from vault.parser import parse_note
from vault.writer import (
    ConflictError,
    NoteSpec,
    PathError,
    SanitizeError,
    TemplateError,
    ValidationError,
    VaultWriter,
    WriterError,
)

BACKEND = Path(__file__).resolve().parents[1]
GOLDEN_VAULT = BACKEND.parents[1] / "second-brain/fixtures/golden-vault/vault"
NOW = datetime(2026, 10, 20, 9, 30, 15)
CREATABLE = conventions.KNOWN_TYPES


def clock() -> datetime:
    return NOW


@pytest.fixture
def vault(isolated_vault):
    """A minimal vault: the six seed templates and nothing else."""
    shutil.copytree(
        GOLDEN_VAULT / conventions.TEMPLATES_FOLDER, isolated_vault / conventions.TEMPLATES_FOLDER
    )
    return isolated_vault


@pytest.fixture
def writer(vault):
    return VaultWriter(vault, clock=clock)


def read(vault: Path, rel: str) -> str:
    return (vault / rel).read_text(encoding="utf-8")


def tree(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*")}


# --- Type to folder, content ---------------------------------------------------------------------


@pytest.mark.parametrize("note_type", [t for t in CREATABLE if t != "daily"])
def test_each_type_goes_to_its_folder_with_a_parseable_note(writer, vault, note_type):
    created = writer.create(note_type, "Sample title")
    assert created.path == f"{conventions.TYPE_FOLDERS[note_type]}/Sample title.md"
    parsed = parse_note(created.path, (vault / created.path).read_bytes())
    assert parsed.parse_error is None
    assert parsed.type == note_type
    assert parsed.note_id == "20261020093015" == created.note_id
    assert str(parsed.frontmatter["created"]) == "2026-10-20"
    assert parsed.status == conventions.DEFAULT_STATUS[note_type]


def test_daily_note_goes_in_the_year_folder_created_on_demand(writer, vault):
    assert not (vault / "01-Daily").exists()
    created = writer.create("daily", "2027-01-05")
    assert created.path == "01-Daily/2027/2027-01-05.md"
    text = read(vault, created.path)
    assert "# Standup - 2027-01-05" in text
    assert "created: 2026-10-20" in text
    assert "status" not in text.split("---")[1]


def test_daily_defaults_to_today_and_rejects_a_non_date(writer):
    assert writer.create("daily").path == "01-Daily/2026/2026-10-20.md"
    for bad in ("2026-13-01", "today", "2026-1-1", "../2026-10-21"):
        with pytest.raises(SanitizeError):
            writer.create("daily", bad)


def test_unknown_type_is_rejected(writer):
    with pytest.raises(ValidationError):
        writer.create("meeting", "x")


def test_template_defaults_and_fields(writer, vault):
    writer.create("project", "Harbor")
    created = writer.create(
        "task", "Fix latch", project="Harbor", priority="high", due="2026-11-02", status="blocked"
    )
    text = read(vault, created.path)
    assert "status: blocked\n" in text
    assert "priority: high\n" in text
    assert "due: 2026-11-02\n" in text
    assert 'project: "[[Harbor]]"\n' in text
    assert text.endswith("## Links\n")


def test_body_is_appended_and_not_templated(writer, vault):
    created = writer.create("capture", "A thought", body="line one\r\n{{title}} stays\r\n")
    text = read(vault, created.path)
    assert text.endswith("tags: []\n---\n\nline one\n{{title}} stays\n")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "nope"},
        {"priority": "urgent"},
        {"due": "2026-02-30"},
        {"due": "tomorrow"},
        {"project": "No Such Project"},
    ],
)
def test_invalid_fields_are_rejected_and_nothing_is_written(writer, vault, kwargs):
    before = tree(vault)
    with pytest.raises(ValidationError):
        writer.create("task", "T", **kwargs)
    assert tree(vault) == before


def test_a_field_the_type_has_no_key_for_is_rejected(writer):
    with pytest.raises(ValidationError):
        writer.create("project", "P", priority="high")
    with pytest.raises(ValidationError):
        writer.create("daily", "2026-10-20", status="active")
    with pytest.raises(ValidationError):
        writer.create("capture", "C", due="2026-10-20")


def test_status_vocabulary_is_per_type(writer):
    assert writer.create("decision", "D", status="accepted").path.endswith("D.md")
    with pytest.raises(ValidationError):
        writer.create("lesson", "L", status="proposed")


# --- Titles and names --------------------------------------------------------------------------


def test_title_is_sanitised_for_the_file_name(writer):
    created = writer.create("task", 'Fix: the "gate" / latch #1')
    assert created.path == "02-Work/Tasks/Fix the gate latch 1.md"
    assert created.title == "Fix the gate latch 1"


def test_empty_title_becomes_untitled_with_timestamp(writer):
    assert writer.create("task", "///").path == "02-Work/Tasks/Untitled 2026-10-20 093015.md"
    assert writer.create("lesson").path == "05-Knowledge/Lessons/Untitled 2026-10-20 093015.md"


def test_capture_without_title_is_named_from_its_first_eight_words(writer):
    created = writer.create("capture", body="one two three four five six seven eight nine ten")
    assert created.path == "00-Inbox/2026-10-20 0930 one two three four five six seven eight.md"


def test_capture_name_collision_retries_once_with_seconds(writer):
    first = writer.create("capture", body="same text")
    second = writer.create("capture", body="same text")
    assert first.path == "00-Inbox/2026-10-20 0930 same text.md"
    assert second.path == "00-Inbox/2026-10-20 093015 same text.md"
    with pytest.raises(ConflictError):
        writer.create("capture", body="same text")


def test_titled_capture_does_not_retry(writer):
    writer.create("capture", "Named")
    with pytest.raises(ConflictError):
        writer.create("capture", "Named")


def test_path_over_200_characters_is_rejected(writer, vault):
    long_title = "x" * 100
    assert len(f"05-Knowledge/Decisions/{long_title}.md") <= 200
    writer.create("decision", long_title)
    assert len("05-Knowledge/Decisions/" + "x" * 100 + ".md") == 126
    with pytest.raises(PathError):
        writer._write_new("05-Knowledge/Decisions/" + "y" * 190 + ".md", "x")


# --- Collisions -------------------------------------------------------------------------------


def test_same_folder_case_insensitive_collision_is_a_conflict(writer, vault):
    writer.create("task", "Fix Gate")
    before = tree(vault)
    with pytest.raises(ConflictError):
        writer.create("task", "fix gate")
    assert tree(vault) == before


def test_same_name_in_another_folder_is_allowed(writer):
    assert writer.create("task", "Shared").path == "02-Work/Tasks/Shared.md"
    assert writer.create("lesson", "Shared").path == "05-Knowledge/Lessons/Shared.md"


def test_collision_reads_the_filesystem_not_the_index(writer, vault):
    folder = vault / "02-Work/Tasks"
    folder.mkdir(parents=True)
    (folder / "By Hand.md").write_text("hand made", encoding="utf-8")
    with pytest.raises(ConflictError):
        writer.create("task", "by hand")
    assert (folder / "By Hand.md").read_text(encoding="utf-8") == "hand made"


def test_two_equal_titles_in_one_operation_conflict_before_any_write(writer, vault):
    before = tree(vault)
    with pytest.raises(ConflictError):
        writer.create_many([NoteSpec("task", "Dup"), NoteSpec("task", "dup")])
    assert tree(vault) == before


def test_duplicate_project_slug_is_a_conflict(writer):
    writer.create("project", "Night Owl")
    with pytest.raises(ConflictError):
        writer.create("project", "Night-Owl")


def test_the_writer_does_not_use_the_database():
    for module in ("writer", "sanitize", "templating"):
        tree_ = ast.parse((BACKEND / "vault" / f"{module}.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree_):
            if isinstance(node, ast.Import):
                imported |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported |= {f"{node.module}.{a.name}" for a in node.names}
        assert not {i for i in imported if i.startswith(("django.db", "vault.models"))}, module


# --- Project links ----------------------------------------------------------------------------


def test_project_link_is_plain_when_the_stem_is_unique(writer, vault):
    writer.create("project", "Harbor Lights")
    created = writer.create("task", "T", project="harbor-lights")  # given as a slug
    assert 'project: "[[Harbor Lights]]"' in read(vault, created.path)
    created = writer.create("lesson", "L", project="[[Harbor Lights|alias]]")
    assert 'project: "[[Harbor Lights]]"' in read(vault, created.path)


def test_project_link_is_folder_qualified_when_the_stem_is_duplicated_on_disk(writer, vault):
    writer.create("project", "Harbor")
    other = vault / "05-Knowledge/Lessons"
    other.mkdir(parents=True)
    (other / "harbor.md").write_text("a lesson with the same stem", encoding="utf-8")
    created = writer.create("task", "T", project="Harbor")
    assert 'project: "[[02-Work/Projects/Harbor]]"' in read(vault, created.path)


def test_project_link_ignores_ignored_files_when_counting_stems(writer, vault):
    writer.create("project", "Harbor")
    hidden = vault / ".trash"
    hidden.mkdir()
    (hidden / "Harbor.md").write_text("trashed", encoding="utf-8")
    created = writer.create("task", "T", project="Harbor")
    assert 'project: "[[Harbor]]"' in read(vault, created.path)


def test_project_made_in_the_same_operation_can_be_linked(writer, vault):
    _, task = writer.create_many(
        [NoteSpec("project", "Fresh"), NoteSpec("task", "T", project="Fresh")]
    )
    assert 'project: "[[Fresh]]"' in read(vault, task.path)


def test_duplicate_project_slugs_on_disk_do_not_resolve(writer, vault):
    folder = vault / "02-Work/Projects"
    folder.mkdir(parents=True)
    (folder / "Night Owl.md").write_text("x", encoding="utf-8")
    (folder / "Night-Owl.md").write_text("x", encoding="utf-8")
    with pytest.raises(ValidationError):
        writer.create("task", "T", project="night-owl")


def test_project_link_survives_awkward_stems(writer, vault):
    writer.create("project", "Q3 \u2028 plan's {x}")
    created = writer.create("task", "T", project="q3-plan-s-x")
    parsed = parse_note(created.path, (vault / created.path).read_bytes())
    assert parsed.parse_error is None
    assert parsed.project == "q3-plan-s-x"


# --- Ids and the clock ------------------------------------------------------------------------


def test_notes_of_one_operation_get_ids_one_second_apart_from_one_clock_read(vault):
    reads = []

    def counting_clock():
        reads.append(1)
        return NOW

    specs = [NoteSpec("task", f"T{i}") for i in range(3)]
    created = VaultWriter(vault, clock=counting_clock).create_many(specs)
    assert [c.note_id for c in created] == ["20261020093015", "20261020093016", "20261020093017"]
    assert len(reads) == 1
    assert "created: 2026-10-20" in read(vault, created[2].path)


def test_ids_wrap_within_the_day_and_keep_the_date(vault):
    late = datetime(2026, 10, 20, 23, 59, 59)
    created = VaultWriter(vault, clock=lambda: late).create_many(
        [NoteSpec("task", "A"), NoteSpec("task", "B")]
    )
    assert [c.note_id for c in created] == ["20261020235959", "20261020000000"]


def test_each_create_call_reads_the_clock_again(vault):
    times = iter([NOW, NOW.replace(second=40)])
    w = VaultWriter(vault, clock=lambda: next(times))
    assert w.create("task", "A").note_id == "20261020093015"
    assert w.create("task", "B").note_id == "20261020093040"


def test_default_clock_uses_the_pinned_date(vault, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    monkeypatch.setenv("SECOND_BRAIN_TODAY", "2026-10-09")
    created = VaultWriter(vault).create("task", "Pinned")
    assert re.fullmatch(r"20261009\d{6}", created.note_id)


# --- Confinement ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rel",
    [
        "../escape.md",
        "02-Work/../../escape.md",
        "02-Work/Tasks/../Tasks/x.md",
        "/etc/x.md",
        "\\windows\\x.md",
        "C:/x.md",
        "02-Work\\Tasks\\x.md",
        "./x.md",
        "02-Work//x.md",
        "",
        "02-Work/Tasks/x.txt",
        "02-Work/Tasks/x",
        "02-Work/Tasks/.md",
        "02-Work/Tasks/.hidden.md",
        ".obsidian/x.md",
        ".trash/x.md",
        "02-Work/.git/x.md",
        "08-System/Templates/task.md",
        "08-system/templates/new.md",
        "02-Work/Tasks/a:b.md",
        "02-Work/Tasks/a\nb.md",
        "03-Elsewhere/x.md",
        "02-Work/Unknown/x.md",
    ],
)
def test_write_new_rejects_unconfined_or_unsuitable_paths(writer, vault, rel):
    before = tree(vault)
    with pytest.raises(PathError):
        writer._write_new(rel, "x")
    assert tree(vault) == before


def test_sbignore_patterns_are_honoured(writer, vault):
    (vault / ".sbignore").write_text("02-Work/Tasks/Secret*\nprivate/\n", encoding="utf-8")
    with pytest.raises(PathError):
        writer.create("task", "Secret plan")
    assert writer.create("task", "Open plan").path == "02-Work/Tasks/Open plan.md"


def test_symlinked_component_is_refused(writer, vault, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (vault / "02-Work").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PathError):
        writer.create("task", "T")
    assert list(outside.iterdir()) == []


def test_symlinked_leaf_folder_is_refused(writer, vault, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (vault / "02-Work").mkdir()
    (vault / "02-Work/Tasks").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PathError):
        writer.create("task", "T")
    assert list(outside.iterdir()) == []


def test_a_symlink_at_the_target_name_is_a_conflict_never_followed(writer, vault, tmp_path):
    target = tmp_path / "victim.md"
    target.write_text("victim", encoding="utf-8")
    folder = vault / "02-Work/Tasks"
    folder.mkdir(parents=True)
    (folder / "T.md").symlink_to(target)
    with pytest.raises(ConflictError):
        writer.create("task", "T")
    assert target.read_text(encoding="utf-8") == "victim"


def test_a_file_where_a_folder_belongs_is_refused(writer, vault):
    (vault / "02-Work").write_text("not a folder", encoding="utf-8")
    with pytest.raises(PathError):
        writer.create("task", "T")


def test_missing_phase_1_folders_are_created_other_folders_are_not(writer, vault):
    assert writer.create("task", "T").path == "02-Work/Tasks/T.md"
    assert (vault / "02-Work/Tasks").is_dir()
    with pytest.raises(PathError):
        writer._write_new("02-Work/Clients/x.md", "x")
    with pytest.raises(PathError):
        writer._write_new("01-Daily/notayear/x.md", "x")
    assert not (vault / "02-Work/Clients").exists()
    writer._write_new("01-Daily/2031/x.md", "x")
    assert (vault / "01-Daily/2031/x.md").is_file()


def test_existing_folders_match_in_any_letter_case(writer, vault):
    (vault / "02-work/tasks").mkdir(parents=True)
    created = writer.create("task", "T")
    assert created.path == "02-work/tasks/T.md"
    assert not (vault / "02-Work").exists() or (vault / "02-Work").samefile(vault / "02-work")


# --- Atomic write -----------------------------------------------------------------------------


def tasks_dir(vault: Path) -> Path:
    return vault / "02-Work/Tasks"


def test_temp_file_uses_the_documented_pattern_and_is_gone_afterwards(writer, vault, monkeypatch):
    seen = []
    real_link = os.link

    def spy(src, dst):
        seen.append((Path(src).name, Path(src).parent, Path(dst)))
        real_link(src, dst)

    monkeypatch.setattr(writer_module.os, "link", spy)
    writer.create("task", "My task")
    ((name, parent, destination),) = seen
    assert re.fullmatch(r"\.My task\.sbw-tmp-[0-9a-f]{8}", name)
    assert parent == destination.parent
    assert [p.name for p in destination.parent.iterdir()] == ["My task.md"]


def test_temp_file_is_removed_when_publishing_fails(writer, vault, monkeypatch):
    def boom(src, dst):
        raise OSError(errno.EIO, "disk on fire", str(src))

    monkeypatch.setattr(writer_module.os, "link", boom)
    with pytest.raises(WriterError, match="disk on fire") as caught:
        writer.create("task", "T")
    assert str(vault) not in str(caught.value)  # no host path in the message
    assert list(tasks_dir(vault).iterdir()) == []


def test_temp_file_is_removed_when_the_write_fails(writer, vault, monkeypatch):
    def boom(fd):
        raise OSError(errno.EIO, "fsync failed")

    monkeypatch.setattr(writer_module.os, "fsync", boom)
    with pytest.raises(WriterError, match="fsync failed"):
        writer.create("task", "T")
    assert list(tasks_dir(vault).iterdir()) == []


def test_temp_file_is_removed_on_an_interrupt(writer, vault, monkeypatch):
    def interrupt(src, dst):
        raise KeyboardInterrupt

    monkeypatch.setattr(writer_module.os, "link", interrupt)
    with pytest.raises(KeyboardInterrupt):
        writer.create("task", "T")
    assert list(tasks_dir(vault).iterdir()) == []


def test_only_a_temp_file_this_call_created_is_removed(writer, vault, monkeypatch):
    tasks_dir(vault).mkdir(parents=True)
    bystander = tasks_dir(vault) / ".T.sbw-tmp-deadbeef"
    bystander.write_text("not ours", encoding="utf-8")
    monkeypatch.setattr(writer_module.secrets, "token_hex", lambda n: "deadbeef")
    with pytest.raises(WriterError):  # os.open(O_EXCL) fails: the name is taken by someone else
        writer.create("task", "T")
    assert bystander.read_text(encoding="utf-8") == "not ours"


def test_target_does_not_exist_until_publish_and_the_temp_is_complete(writer, vault, monkeypatch):
    """A crash between the temp write and the publish leaves the target absent; the finished temp
    (ignored: dot-prefixed, not `.md`) is all that remains."""
    state = {}
    real_link = os.link

    def crash_point(src, dst):
        state["target_exists"] = Path(dst).exists()
        state["temp_text"] = Path(src).read_text(encoding="utf-8")
        real_link(src, dst)

    monkeypatch.setattr(writer_module.os, "link", crash_point)
    created = writer.create("task", "T")
    assert state["target_exists"] is False
    assert state["temp_text"] == read(vault, created.path)


def test_a_failed_create_never_touches_an_existing_file(writer, vault, monkeypatch):
    tasks_dir(vault).mkdir(parents=True)
    (tasks_dir(vault) / "T.md").write_text("original", encoding="utf-8")
    monkeypatch.setattr(writer_module.os, "link", lambda s, d: pytest.fail("linked"))
    monkeypatch.setattr(writer_module.os, "replace", lambda s, d: pytest.fail("replaced"))
    with pytest.raises(ConflictError):
        writer.create("task", "T")
    assert (tasks_dir(vault) / "T.md").read_text(encoding="utf-8") == "original"
    assert [p.name for p in tasks_dir(vault).iterdir()] == ["T.md"]


def test_a_file_that_appears_after_the_check_is_not_overwritten(writer, vault, monkeypatch):
    """The existence check says no, then the name is taken: the link refuses, nothing is lost."""
    tasks_dir(vault).mkdir(parents=True)
    (tasks_dir(vault) / "T.md").write_text("someone else", encoding="utf-8")
    monkeypatch.setattr(writer_module, "_exists_ci", lambda directory, name: False)
    monkeypatch.setattr(writer_module.os, "replace", lambda s, d: pytest.fail("replaced"))
    with pytest.raises(ConflictError):
        writer._write_new("02-Work/Tasks/T.md", "mine")
    assert [p.name for p in tasks_dir(vault).iterdir()] == ["T.md"]
    assert (tasks_dir(vault) / "T.md").read_text(encoding="utf-8") == "someone else"


def test_two_threads_creating_the_same_title_one_wins(vault):
    folder = tasks_dir(vault)
    folder.mkdir(parents=True)
    barrier = threading.Barrier(2)
    outcomes: list[object] = [None, None]

    def run(index: int) -> None:
        w = VaultWriter(vault, clock=clock)
        barrier.wait()
        try:
            outcomes[index] = w.create("task", "Race", body=f"body {index}")
        except ConflictError as exc:
            outcomes[index] = exc

    threads = [threading.Thread(target=run, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    winners = [o for o in outcomes if not isinstance(o, Exception)]
    assert len(winners) == 1
    assert sum(isinstance(o, ConflictError) for o in outcomes) == 1
    assert [p.name for p in folder.iterdir()] == ["Race.md"]
    assert f"body {outcomes.index(winners[0])}" in (folder / "Race.md").read_text(encoding="utf-8")


def test_two_publishes_racing_past_the_check_one_wins(vault, monkeypatch):
    """Both writers pass the existence check (forced), so only the link decides."""
    monkeypatch.setattr(writer_module, "_exists_ci", lambda directory, name: False)
    tasks_dir(vault).mkdir(parents=True)
    barrier = threading.Barrier(2)
    results: list[str] = []

    def run(index: int) -> None:
        barrier.wait()
        try:
            VaultWriter(vault, clock=clock)._write_new("02-Work/Tasks/R.md", f"mine {index}")
            results.append(f"won {index}")
        except ConflictError:
            results.append("lost")

    threads = [threading.Thread(target=run, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(r.split()[0] for r in results) == ["lost", "won"]
    winner = next(r for r in results if r.startswith("won")).split()[1]
    assert (tasks_dir(vault) / "R.md").read_text(encoding="utf-8") == f"mine {winner}"
    assert [p.name for p in tasks_dir(vault).iterdir()] == ["R.md"]


@pytest.mark.parametrize("code", [errno.EPERM, errno.ENOTSUP, errno.EXDEV])
def test_filesystems_without_hard_links_fall_back_to_replace(
    writer, vault, monkeypatch, caplog, code
):
    def refuse(src, dst):
        raise OSError(code, "links not supported")

    monkeypatch.setattr(writer_module.os, "link", refuse)
    with caplog.at_level(logging.WARNING, logger="vault.writer"):
        created = writer.create("task", "Fallback")
    assert read(vault, created.path).startswith("---\ntype: task")
    assert [p.name for p in tasks_dir(vault).iterdir()] == ["Fallback.md"]
    assert any("os.replace" in record.getMessage() for record in caplog.records)


def test_fallback_still_refuses_a_name_taken_meanwhile(writer, vault, monkeypatch):
    tasks_dir(vault).mkdir(parents=True)
    calls = []

    def exists(directory, name):
        calls.append(name)
        if len(calls) == 1:
            return False
        (directory / name).write_text("someone else", encoding="utf-8")
        return True

    monkeypatch.setattr(writer_module, "_exists_ci", exists)
    monkeypatch.setattr(
        writer_module.os, "link", lambda s, d: (_ for _ in ()).throw(OSError(errno.EPERM, "x"))
    )
    with pytest.raises(ConflictError):
        writer._write_new("02-Work/Tasks/T.md", "mine")
    assert [p.name for p in tasks_dir(vault).iterdir()] == ["T.md"]


def test_directory_fsync_failure_does_not_fail_the_create(writer, vault, monkeypatch):
    real_fsync = os.fsync
    state = {"calls": 0}

    def fsync(fd):
        state["calls"] += 1
        if state["calls"] == 2:  # the first is the file, the second the directory
            raise OSError(errno.EINVAL, "not supported")
        real_fsync(fd)

    monkeypatch.setattr(writer_module.os, "fsync", fsync)
    assert writer.create("task", "T").path == "02-Work/Tasks/T.md"
    assert state["calls"] == 2


# --- File format and ownership ----------------------------------------------------------------


def test_created_files_are_lf_utf8_without_bom(writer, vault):
    created = writer.create("task", "Caf\u00e9 \u65e5\u672c", body="a\r\nb\rc")
    data = (vault / created.path).read_bytes()
    assert b"\r" not in data
    assert not data.startswith(b"\xef\xbb\xbf")
    assert data.decode("utf-8").endswith("a\nb\nc\n")
    assert data.endswith(b"\n") and not data.endswith(b"\n\n")


def test_crlf_template_still_produces_lf(writer, vault):
    template = vault / conventions.TEMPLATES_FOLDER / "task.md"
    template.write_bytes(template.read_bytes().replace(b"\n", b"\r\n"))
    created = writer.create("task", "T")
    assert b"\r" not in (vault / created.path).read_bytes()


def test_owner_and_mode_local_filesystem_sanity_check(writer, vault):
    """A local-filesystem sanity check only. On the real drvfs mount (spike M7) every file shows
    as uid/gid 1000, mode 0777 whoever created it; this proves nothing about that mount. It only
    checks the writer creates files and folders as the running user."""
    created = writer.create("task", "T")
    info = (vault / created.path).stat()
    assert info.st_uid == os.getuid()
    assert info.st_gid == os.getgid()
    assert (vault / "02-Work/Tasks").stat().st_uid == os.getuid()


# --- Templates come from the vault ------------------------------------------------------------


def test_templates_are_read_from_the_vault_copy(writer, vault):
    template = vault / conventions.TEMPLATES_FOLDER / "task.md"
    template.write_text(
        template.read_text(encoding="utf-8").replace("## Description", "## My own heading"),
        encoding="utf-8",
    )
    assert "## My own heading" in read(vault, writer.create("task", "T").path)


def test_a_template_with_an_unsupported_token_is_an_error_and_writes_nothing(writer, vault):
    template = vault / conventions.TEMPLATES_FOLDER / "task.md"
    template.write_text(template.read_text(encoding="utf-8") + "{{author}}\n", encoding="utf-8")
    before = tree(vault)
    with pytest.raises(TemplateError):
        writer.create("task", "T")
    assert tree(vault) == before


def test_a_missing_template_is_an_error(writer, vault):
    (vault / conventions.TEMPLATES_FOLDER / "lesson.md").unlink()
    with pytest.raises(TemplateError):
        writer.create("lesson", "L")


def test_the_real_vault_is_never_the_default(vault):
    assert "Second Brain" not in str(VaultWriter(vault).root)
    assert "/mnt/d/Second Brain" not in Path(writer_module.__file__).read_text(encoding="utf-8")


# --- Acceptance: the conformance checker passes after creates ---------------------------------


def create_one_of_each(root: Path) -> list[str]:
    """One note of every type in one operation, so the ids are distinct (C20)."""
    created = VaultWriter(root, clock=clock).create_many(
        [
            NoteSpec("project", "Acceptance Project"),
            NoteSpec(
                "task",
                "Acceptance task",
                project="Acceptance Project",
                priority="low",
                due="2026-11-01",
            ),
            NoteSpec("decision", "Acceptance decision", project="Acceptance Project"),
            NoteSpec("lesson", "Acceptance lesson", project="Acceptance Project"),
            NoteSpec("capture", body="Acceptance capture text"),
            NoteSpec("daily", "2026-10-20"),
        ]
    )
    return [note.path for note in created]


def test_conformance_passes_on_a_minimal_vault_after_creates(vault, capsys):
    create_one_of_each(vault)
    assert conformance.check_vault(vault) == []
    assert conformance.main([str(vault)]) == conformance.EXIT_OK
    assert capsys.readouterr().out == ""


def test_conformance_findings_on_a_golden_copy_do_not_change_after_creates(
    isolated_vault, tmp_path
):
    """The golden vault has deliberate findings; creates must add none of their own."""
    copy = tmp_path / "golden-copy"
    shutil.copytree(GOLDEN_VAULT, copy)
    before = conformance.check_vault(copy)
    created = create_one_of_each(copy)
    after = conformance.check_vault(copy)
    assert after == before
    assert not {f.path for f in after} & set(created)


# --- Review fixes: links, caps, validation, names ----------------------------------------------


def test_a_note_named_like_its_project_gets_the_qualified_link(writer, vault):
    writer.create("project", "LoadUp")
    created = writer.create("task", "LoadUp", project="loadup")
    assert 'project: "[[02-Work/Projects/LoadUp]]"' in read(vault, created.path)


def test_the_note_being_created_counts_in_the_same_operation_too(writer, vault):
    _, task = writer.create_many(
        [NoteSpec("project", "LoadUp"), NoteSpec("task", "loadup", project="LoadUp")]
    )
    assert 'project: "[[02-Work/Projects/LoadUp]]"' in read(vault, task.path)


def test_a_body_over_one_mebibyte_is_rejected(writer, vault):
    before = tree(vault)
    with pytest.raises(ValidationError):
        writer.create("capture", "Big", body="x" * (writer_module.MAX_BODY_BYTES + 1))
    assert tree(vault) == before
    writer.create("capture", "Fits", body="x" * writer_module.MAX_BODY_BYTES)


def test_more_than_fifty_notes_per_operation_are_rejected(writer, vault):
    before = tree(vault)
    with pytest.raises(ValidationError):
        writer.create_many([NoteSpec("task", f"T{i}") for i in range(51)])
    assert tree(vault) == before
    assert len(writer.create_many([NoteSpec("task", f"T{i}") for i in range(50)])) == 50


def test_ids_can_never_wrap_past_a_day_of_seconds():
    operation = writer_module._Operation(Path("."), NOW)
    assert operation.at(writer_module.MAX_IDS_PER_DAY - 1).second == NOW.second - 1
    with pytest.raises(ValidationError):
        operation.at(writer_module.MAX_IDS_PER_DAY)


def test_default_clock_reads_the_clock_once(monkeypatch):
    from django.utils import timezone

    reads = []
    real = timezone.localtime

    def once():
        reads.append(1)
        return real()

    monkeypatch.setattr(writer_module.timezone, "localtime", once)
    monkeypatch.setattr(writer_module.vault_clock, "today", lambda: pytest.fail("second read"))
    writer_module.default_clock()
    assert len(reads) == 1


def test_frontmatter_block_may_end_with_three_dots(writer, vault):
    template = vault / conventions.TEMPLATES_FOLDER / "task.md"
    text = template.read_text(encoding="utf-8").replace(
        "tags: []\n---\n", "tags: []\n...\npriority: x\n"
    )
    template.write_text(text, encoding="utf-8")
    created = writer.create("task", "T", priority="high")
    body = read(vault, created.path)
    assert "priority: high\n" in body.split("\n...\n")[0]
    assert "priority: x" in body.split("\n...\n")[1]


def test_exceptions_share_a_base_and_keep_value_error():
    for error in (PathError, ConflictError, ValidationError, SanitizeError, TemplateError):
        assert issubclass(error, WriterError)
    assert issubclass(SanitizeError, ValueError)
    assert issubclass(TemplateError, ValueError)


def test_the_error_message_names_no_host_path(writer, vault, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError(errno.EACCES, "Permission denied", str(vault / "02-Work"))

    monkeypatch.setattr(writer_module.os, "mkdir", boom)
    with pytest.raises(WriterError) as caught:
        writer.create("task", "T")
    assert str(vault) not in str(caught.value)


@pytest.mark.parametrize(
    "rel", ["02-Work/Tasks/CON.md", "02-Work/aux/x.md", "02-Work/Tasks/LPT\u00b9.md"]
)
def test_reserved_device_names_in_any_segment_are_rejected(writer, rel):
    with pytest.raises(PathError):
        writer._write_new(rel, "x")


def test_a_reserved_title_gets_a_usable_name(writer):
    assert writer.create("task", "NUL.report").path == "02-Work/Tasks/NUL note.report.md"


def test_path_cap_is_measured_in_utf16_units(writer):
    stem = "\U0001f600" * 58  # 116 UTF-16 units: fine alone, too long with the folder
    assert writer.create("capture", stem).path.endswith(".md")
    with pytest.raises(PathError):
        writer._write_new("05-Knowledge/Decisions/" + "\U0001f600" * 90 + ".md", "x")


def test_yaml_quoting_escapes_every_control_and_format_character():
    quoted = writer_module._yaml_double_quoted('a"b\\c\u200d\u2028\x85\x00z')
    assert quoted == '"a\\"b\\\\c\\u200d\\u2028\\u0085\\u0000z"'


def test_a_template_with_the_wrong_type_is_a_template_error(writer, vault):
    template = vault / conventions.TEMPLATES_FOLDER / "task.md"
    template.write_text(
        template.read_text(encoding="utf-8").replace("type: task", "type: lesson"), encoding="utf-8"
    )
    before = tree(vault)
    with pytest.raises(TemplateError):
        writer.create("task", "T")
    assert tree(vault) == before


def test_a_template_with_broken_frontmatter_is_a_template_error(writer, vault):
    template = vault / conventions.TEMPLATES_FOLDER / "task.md"
    template.write_text("---\ntype: task\nbroken: [\n---\n", encoding="utf-8")
    with pytest.raises(TemplateError):
        writer.create("task", "T")


def test_importing_the_writer_does_not_import_the_models():
    code = "import sys, vault.writer; assert 'vault.models' not in sys.modules, 'models imported'"
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_lone_surrogates_are_a_validation_error(writer, vault):
    before = tree(vault)
    for kwargs in ({"title": "a\ud800b"}, {"title": "ok", "body": "x\udfffy"}):
        with pytest.raises(ValidationError):
            writer.create("task", **kwargs)
    assert tree(vault) == before


def test_joiner_titles_round_trip_into_the_file_name(writer):
    family = "\U0001f468\u200d\U0001f469"
    assert writer.create("task", family).path == f"02-Work/Tasks/{family}.md"


def test_an_unreadable_sbignore_is_a_writer_error(writer, vault):
    (vault / ".sbignore").mkdir()
    with pytest.raises(WriterError) as caught:
        writer.create("task", "T")
    assert str(vault) not in str(caught.value)


def test_a_folder_created_by_another_writer_in_between_is_accepted(writer, vault, monkeypatch):
    real_mkdir = os.mkdir

    def racing_mkdir(path, *args, **kwargs):
        real_mkdir(path, *args, **kwargs)
        real_mkdir(path)  # raises FileExistsError, as if we lost the race

    monkeypatch.setattr(writer_module.os, "mkdir", racing_mkdir)
    assert writer.create("task", "T").path == "02-Work/Tasks/T.md"


def test_a_symlink_that_wins_the_mkdir_race_is_refused(writer, vault, tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()

    def racing_mkdir(path, *args, **kwargs):
        Path(path).symlink_to(outside, target_is_directory=True)
        raise FileExistsError(errno.EEXIST, "exists")

    monkeypatch.setattr(writer_module.os, "mkdir", racing_mkdir)
    with pytest.raises(PathError):
        writer.create("task", "T")
    assert list(outside.iterdir()) == []
