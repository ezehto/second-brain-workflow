"""Tests for the indexer (plan 2.7, 2.9, task P1-21)."""

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import connection, connections
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from vault import indexer
from vault.indexer import Indexer
from vault.models import Link, Note, Tag

GOLDEN = Path(__file__).resolve().parents[3] / "second-brain/fixtures/golden-vault"

pytestmark = pytest.mark.django_db


class CountingOpener:
    def __init__(self):
        self.opened = []

    def __call__(self, path):
        self.opened.append(path)
        return Path(path).read_bytes()


@pytest.fixture
def vault(isolated_vault):
    shutil.copytree(GOLDEN / "vault", isolated_vault, dirs_exist_ok=True)
    return isolated_vault


def expected_paths():
    return set(json.loads((GOLDEN / "expected/index.json").read_text())["notes"])


def write(vault, rel, text):
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def paths():
    return set(Note.objects.values_list("path", flat=True))


def test_first_sync_indexes_exactly_the_non_ignored_notes(vault):
    summary = indexer.sync(vault)
    assert paths() == expected_paths()
    assert summary.scanned == summary.read == summary.added == len(expected_paths())
    assert summary.changed == summary.removed == 0
    assert Note.objects.get(path=sorted(paths())[0]).file_mtime.tzinfo is not None


def test_summary_is_one_json_line(vault):
    data = json.loads(indexer.sync(vault).to_json())
    assert list(data)[:9] == [
        "duration_s",
        "scanned",
        "read",
        "added",
        "changed",
        "removed",
        "moved",
        "over_budget",
        "index_parse_errors",
    ]


def test_edit_add_delete(vault):
    idx = Indexer()
    idx.sync(vault)
    target = sorted(paths())[0]
    write(vault, target, "---\nid: 1\ntags: [fresh]\n---\nbody [[Other Note]] #inline\n")
    write(vault, "New.md", "hello [[Target]]")
    gone = sorted(paths())[1]
    (vault / gone).unlink()
    summary = idx.sync(vault)
    assert (summary.changed, summary.added, summary.removed) == (1, 1, 1)
    note = Note.objects.get(path=target)
    assert note.note_id == "1"
    assert set(note.tags.values_list("name", flat=True)) == {"fresh", "inline"}
    assert set(note.links.values_list("target_title", flat=True)) == {"other note"}
    assert list(Note.objects.get(path="New.md").links.values_list("target_title", flat=True)) == [
        "target"
    ]
    assert not Note.objects.filter(path=gone).exists()


def test_rename_without_id_is_delete_plus_add_and_not_moved(vault, caplog):
    write(vault, "Old.md", "no id")
    idx = Indexer()
    idx.sync(vault)
    (vault / "Old.md").rename(vault / "New.md")
    with caplog.at_level(logging.INFO, logger="vault.indexer"):
        summary = idx.sync(vault)
    assert (summary.added, summary.removed, summary.moved) == (1, 1, 0)
    assert "moved:" not in caplog.text
    assert not Note.objects.filter(path="Old.md").exists()


def test_rename_with_matching_id_is_logged_as_moved(vault, caplog):
    write(vault, "Old.md", "---\nid: 20260101000000\n---\nx")
    idx = Indexer()
    idx.sync(vault)
    (vault / "Sub").mkdir()
    (vault / "Old.md").rename(vault / "Sub" / "New.md")
    with caplog.at_level(logging.INFO, logger="vault.indexer"):
        summary = idx.sync(vault)
    assert (summary.added, summary.removed, summary.moved) == (1, 1, 1)
    assert "moved: Old.md -> Sub/New.md" in caplog.text
    assert Note.objects.get(path="Sub/New.md").note_id == "20260101000000"


def test_unchanged_pass_opens_no_file(vault):
    opener = CountingOpener()
    idx = Indexer(opener)
    idx.sync(vault)
    idx.sync(vault)  # racy rule: everything read last pass is read once more
    opener.opened.clear()
    summary = idx.sync(vault)
    assert opener.opened == []
    assert summary.read == 0 and summary.scanned == len(expected_paths())


def test_racy_rule_rereads_files_read_in_the_previous_pass(vault):
    opener = CountingOpener()
    idx = Indexer(opener)
    target = write(vault, "Racy.md", "aaaa")
    idx.sync(vault)
    before = target.stat()
    target.write_text("bbbb")  # same size
    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))  # same mtime too
    summary = idx.sync(vault)
    assert summary.changed == 1
    assert target in opener.opened[-summary.read :]
    assert Note.objects.get(path="Racy.md").body == "bbbb"
    idx.sync(vault)  # the changed file is read once more, as it was read last pass
    opener.opened.clear()
    idx.sync(vault)  # trusted by stat now
    assert opener.opened == []


def test_a_fresh_indexer_rereads_because_the_memory_is_in_the_index(vault):
    indexer.sync(vault)
    target = vault / sorted(paths())[0]
    before = target.stat()
    data = target.read_bytes()
    target.write_bytes(data[:-1] + (b"X" if data[-1:] != b"X" else b"Y"))
    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert indexer.sync(vault).read == len(expected_paths())
    assert Note.objects.get(path=target.relative_to(vault).as_posix()).body.endswith(("X", "Y"))


def test_force_reads_everything(vault):
    indexer.sync(vault)
    assert indexer.sync(vault, force=True).read == len(expected_paths())


def test_duplicate_and_missing_ids_are_counted(vault):
    base = indexer.sync(vault)
    write(vault, "A.md", "---\nid: 5\n---\n")
    write(vault, "B.md", "---\nid: 5\n---\n")
    write(vault, "C.md", "no id")
    summary = indexer.sync(vault)
    assert summary.index_duplicate_ids == base.index_duplicate_ids + 1
    assert summary.index_missing_ids == base.index_missing_ids + 1
    assert Note.objects.filter(note_id="5").count() == 2  # stored as is


def test_overlong_values_are_nulled_or_skipped_and_flagged(vault):
    long_text = "x" * 1001
    write(
        vault,
        "Long.md",
        f"---\nstatus: {long_text}\ntype: {long_text}\n---\n[[{'t' * 2001}]] #{'g' * 2001}\n",
    )
    summary = indexer.sync(vault)
    note = Note.objects.get(path="Long.md")
    assert note.status is None and note.type == "note"
    assert note.links.count() == 0 and note.tags.count() == 0
    assert "status" in note.parse_error and "tag" in note.parse_error
    assert summary.index_parse_errors >= 1


def test_vanished_file_is_not_an_error(vault):
    write(vault, "Gone.md", "x")

    def opener(path):
        if path.name == "Gone.md":
            raise FileNotFoundError
        return path.read_bytes()

    indexer.sync(vault, indexer=Indexer(opener))
    assert "Gone.md" not in paths()


def test_index_single_file(vault):
    indexer.sync(vault)
    target = sorted(paths())[0]
    other = sorted(paths())[1]
    other_hash = Note.objects.get(path=other).content_hash
    write(vault, target, "---\nid: 9\n---\nsingle")
    write(vault, other, "changed but not reindexed")
    note = indexer.index_single_file(vault, target)
    assert note.note_id == "9" and note.body.strip() == "single"
    assert Note.objects.get(path=other).content_hash == other_hash
    (vault / target).unlink()
    assert indexer.index_single_file(vault, target) is None
    assert not Note.objects.filter(path=target).exists()


def test_sbignore_is_honoured(vault):
    write(vault, ".sbignore", "Skipme/\n")
    write(vault, "Skipme/S.md", "s")
    indexer.sync(vault)
    assert "Skipme/S.md" not in paths()
    (vault / ".sbignore").unlink()
    indexer.sync(vault)
    assert "Skipme/S.md" in paths()


def test_over_budget_is_flagged(vault, monkeypatch):
    monkeypatch.setattr(indexer, "STEADY_BUDGET_SECONDS", -1.0)
    assert indexer.sync(vault).over_budget is True


@pytest.mark.django_db(transaction=True)
def test_advisory_lock_blocks_a_concurrent_pass(vault):
    held, release, finished = threading.Event(), threading.Event(), threading.Event()

    def holder():
        try:
            from django.db import transaction

            with transaction.atomic():
                indexer._lock()
                held.set()
                release.wait(10)
        finally:
            connections.close_all()

    def passer():
        try:
            indexer.sync(vault)
            finished.set()
        finally:
            connections.close_all()

    first = threading.Thread(target=holder)
    first.start()
    assert held.wait(10)
    second = threading.Thread(target=passer)
    second.start()
    assert not finished.wait(1.0)  # blocked on the lock
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", [indexer.LOCK_KEY])
        assert cursor.fetchone()[0] is False
    release.set()
    first.join(10)
    second.join(20)
    assert finished.is_set()
    assert paths() == expected_paths()


def test_reindex_truncates_only_the_index_tables(vault):
    get_user_model().objects.create_user("u", password="p")
    Session.objects.create(
        session_key="abc", session_data="x", expire_date=timezone.now() + timezone.timedelta(days=1)
    )
    indexer.sync(vault)
    Tag.objects.create(name="orphan")
    summary = indexer.reindex(vault)
    assert not Tag.objects.filter(name="orphan").exists()
    assert summary.read == len(expected_paths()) == Note.objects.count()
    assert get_user_model().objects.filter(username="u").exists()
    assert Session.objects.filter(session_key="abc").exists()
    assert Link.objects.exists()


def test_reindex_sql_has_no_cascade(vault):
    with CaptureQueriesContext(connection) as queries:
        indexer.reindex(vault)
    truncates = [q["sql"] for q in queries if q["sql"].startswith("TRUNCATE")]
    assert len(truncates) == 1 and "CASCADE" not in truncates[0].upper()
    for table in ("vault_note", "vault_link", "vault_tag", "vault_note_tags"):
        assert f'"{table}"' in truncates[0]


def test_unused_tags_are_deleted_after_a_pass_and_a_single_file_index(vault):
    write(vault, "T.md", "#only-here")
    indexer.sync(vault)
    assert Tag.objects.filter(name="only-here").exists()
    write(vault, "T.md", "plain")
    indexer.sync(vault)
    assert not Tag.objects.filter(name="only-here").exists()
    write(vault, "T.md", "#again")
    indexer.index_single_file(vault, "T.md")
    write(vault, "T.md", "plain")
    indexer.index_single_file(vault, "T.md")
    assert not Tag.objects.filter(name="again").exists()


def test_reread_next_is_set_on_store_and_cleared_by_a_matching_reread(vault):
    write(vault, "R.md", "x")
    indexer.sync(vault)
    assert Note.objects.get(path="R.md").reread_next is True
    indexer.sync(vault)
    assert Note.objects.get(path="R.md").reread_next is False
    indexer.index_single_file(vault, "R.md")
    assert Note.objects.get(path="R.md").reread_next is True


def test_single_file_reread_flag_is_honoured_by_a_fresh_process_pass(vault):
    target = write(vault, "R.md", "aaaa")
    indexer.sync(vault)
    indexer.sync(vault)
    before = target.stat()
    indexer.index_single_file(vault, "R.md")
    target.write_text("bbbb")
    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
    indexer.sync(vault)
    assert Note.objects.get(path="R.md").body == "bbbb"


@pytest.mark.parametrize(
    "bad",
    [
        "/etc/passwd.md",
        "../x.md",
        "a/../../x.md",
        "",
        "a\x00.md",
        "a//b.md",
        "./c.md",
        "a/./b.md",
        "a/b/",
        "a\\b.md",
    ],
)
def test_single_file_rejects_paths_outside_the_vault(vault, bad):
    with pytest.raises(ValueError):
        indexer.index_single_file(vault, bad)


def test_single_file_never_reads_outside_through_a_symlink(vault, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "Out.md").write_text("secret")
    (vault / "Link.md").symlink_to(outside / "Out.md")
    (vault / "Dir").symlink_to(outside, target_is_directory=True)
    opener = CountingOpener()
    idx = Indexer(opener)
    assert idx.index_single_file(vault, "Link.md") is None
    assert idx.index_single_file(vault, "Dir/Out.md") is None
    assert opener.opened == []
    assert not Note.objects.filter(path__in=["Link.md", "Dir/Out.md"]).exists()


def test_single_file_treats_a_directory_named_md_as_gone(vault):
    write(vault, "x.md", "was a file")
    indexer.index_single_file(vault, "x.md")
    (vault / "x.md").unlink()
    (vault / "x.md").mkdir()
    assert indexer.index_single_file(vault, "x.md") is None
    assert not Note.objects.filter(path="x.md").exists()


def test_a_directory_named_md_is_not_a_note_in_a_pass(vault):
    (vault / "dir.md").mkdir()
    indexer.sync(vault)
    assert "dir.md" not in paths()


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read a chmod 000 file")
def test_an_unreadable_file_is_skipped_with_a_warning(vault, caplog):
    secret = write(vault, "Locked.md", "x")
    write(vault, "Fine.md", "y")
    secret.chmod(0)
    try:
        with caplog.at_level(logging.WARNING, logger="vault.indexer"):
            summary = indexer.sync(vault)
    finally:
        secret.chmod(0o644)
    assert "could not read Locked.md" in caplog.text
    assert "Fine.md" in paths() and "Locked.md" not in paths()
    assert summary.added == len(expected_paths()) + 1


def test_an_unreadable_file_is_skipped_via_opener_error(vault, caplog):
    write(vault, "Locked.md", "x")

    def opener(path):
        if path.name == "Locked.md":
            raise PermissionError("denied")
        return path.read_bytes()

    with caplog.at_level(logging.WARNING, logger="vault.indexer"):
        indexer.sync(vault, indexer=Indexer(opener))
    assert "Locked.md" not in paths() and paths() == expected_paths()


def test_a_path_over_the_column_limit_is_skipped_with_a_warning(vault, caplog):
    folder = "d" * 100
    rel = "/".join([folder] * 10) + "/" + "n" * 40 + ".md"
    assert len(rel) > 1024
    try:
        write(vault, rel, "x")
    except OSError:
        pytest.skip("filesystem refuses the long path")
    with caplog.at_level(logging.WARNING, logger="vault.indexer"):
        summary = indexer.sync(vault)
    assert "path longer than 1024" in caplog.text
    assert rel not in paths() and summary.added == len(expected_paths())
    assert indexer.index_single_file(vault, rel) is None


def test_overlong_link_target_is_flagged(vault):
    write(vault, "L.md", f"[[{'t' * 2001}]] [[ok]]")
    indexer.sync(vault)
    note = Note.objects.get(path="L.md")
    assert "link target longer than 2000" in note.parse_error
    assert list(note.links.values_list("target_title", flat=True)) == ["ok"]


def test_parser_error_comes_first_in_the_joined_parse_error(vault):
    write(vault, "M.md", f"---\n- not a mapping\n---\n[[{'t' * 2001}]]")
    indexer.sync(vault)
    error = Note.objects.get(path="M.md").parse_error
    assert "; " in error and error.index("link target") > 0
    parser_part = error.split("; link target")[0]
    assert parser_part and "link target" not in parser_part


@pytest.mark.django_db(transaction=True)
def test_one_shot_commands_print_exactly_one_json_line(vault):
    # A subprocess sees only committed rows, so run against the test database by name.
    env = {
        **os.environ,
        "VAULT_ROOT": str(vault),
        "POSTGRES_DB": connection.settings_dict["NAME"],
    }
    for command in ("sync_vault", "reindex"):
        done = subprocess.run(
            [sys.executable, "manage.py", command],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        lines = done.stdout.strip().splitlines()
        assert len(lines) == 1, done.stdout
        assert json.loads(lines[0])["scanned"] == len(expected_paths())


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read a chmod 000 file")
@pytest.mark.django_db(transaction=True)
def test_one_shot_warning_goes_to_stderr_and_stdout_stays_one_json_line(vault):
    locked = write(vault, "Locked.md", "x")
    locked.chmod(0)
    env = {
        **os.environ,
        "VAULT_ROOT": str(vault),
        "POSTGRES_DB": connection.settings_dict["NAME"],
    }
    try:
        done = subprocess.run(
            [sys.executable, "manage.py", "sync_vault"],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
    finally:
        locked.chmod(0o644)
    lines = done.stdout.strip().splitlines()
    assert len(lines) == 1, done.stdout
    json.loads(lines[0])
    assert "could not read Locked.md" in done.stderr
