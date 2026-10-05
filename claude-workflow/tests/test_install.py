"""Tests for claude-workflow/install.sh.

Each test copies install.sh into a throwaway dummy source tree (the script
installs from its own directory) and targets a throwaway directory. Nothing
here touches the real ~/.claude.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "install.sh"
MANIFEST = ".second-brain-manifest"
HEADER = "# second-brain install manifest v2"
HEADER_V1 = "# second-brain install manifest v1"
ZERO = "0" * 64


@pytest.fixture
def src(tmp_path):
    root = tmp_path / "src"
    (root / "skills" / "second-brain" / "reference").mkdir(parents=True)
    (root / "commands").mkdir()
    (root / "skills" / "second-brain" / "SKILL.md").write_text("skill v1\n")
    (root / "skills" / "second-brain" / "reference" / "naming.md").write_text("naming\n")
    (root / "commands" / "capture.md").write_text("capture v1\n")
    (root / "commands" / "triage.md").write_text("triage v1\n")
    (root / "commands" / "notes.txt").write_text("not a command\n")
    shutil.copy(SCRIPT, root / "install.sh")
    return root


@pytest.fixture
def target(tmp_path):
    t = tmp_path / "target dir"  # space on purpose
    t.mkdir()
    return t


def run(src, *args, home=None, cwd=None, env=None):
    full_env = {**os.environ, "HOME": str(src.parent / "fake-home" if home is None else home), **(env or {})}
    return subprocess.run(
        ["bash", str(src / "install.sh"), *map(str, args)],
        capture_output=True, text=True, env=full_env, cwd=cwd,
    )


def install(src, target, *extra):
    return run(src, "--target", target, *extra)


def snapshot(root):
    """Map of relative path -> (kind, content) for everything under root."""
    out = {}
    for p in sorted(Path(root).rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_symlink():
            out[rel] = ("link", os.readlink(p))
        elif p.is_dir():
            out[rel] = ("dir", None)
        else:
            out[rel] = ("file", p.read_bytes())
    return out


def manifest_entries(target):
    lines = (target / MANIFEST).read_text().splitlines()
    assert lines[0] == HEADER
    return lines[1:]


def manifest_files(target):
    return {e[2 + 64 + 1:] for e in manifest_entries(target) if e[0] == "F"}


def manifest_dirs(target):
    return {e[2:] for e in manifest_entries(target) if e[0] == "D"}


def test_installs_skill_and_commands_by_copy(src, target):
    r = install(src, target)
    assert r.returncode == 0, r.stderr
    assert (target / "skills/second-brain/SKILL.md").read_text() == "skill v1\n"
    assert (target / "skills/second-brain/reference/naming.md").read_text() == "naming\n"
    assert (target / "commands/capture.md").read_text() == "capture v1\n"
    assert (target / "commands/triage.md").read_text() == "triage v1\n"
    assert not (target / "commands/notes.txt").exists()
    assert not (target / "commands/capture.md").is_symlink()
    assert not (target / "skills").is_symlink()


def test_manifest_lists_installed_files_and_created_dirs(src, target):
    install(src, target)
    entries = manifest_entries(target)
    assert {e[2 + 64 + 1:] for e in entries if e[0] == "F"} == {
        "skills/second-brain/SKILL.md",
        "skills/second-brain/reference/naming.md",
        "commands/capture.md",
        "commands/triage.md",
    }
    assert {e[2:] for e in entries if e[0] == "D"} == {
        "skills", "skills/second-brain", "skills/second-brain/reference", "commands",
    }


def test_creates_missing_target(src, tmp_path):
    t = tmp_path / "new" / "claude"
    # parent missing: the script creates the target (mkdir -p)
    r = install(src, t)
    assert r.returncode == 0, r.stderr
    assert (t / "commands/capture.md").exists()


def test_rerun_updates_in_place_and_removes_stale(src, target):
    install(src, target)
    (src / "skills/second-brain/SKILL.md").write_text("skill v2\n")
    (src / "commands/triage.md").unlink()
    (src / "commands/task.md").write_text("task v1\n")
    (src / "skills/second-brain/reference/naming.md").unlink()
    (src / "skills/second-brain/reference").rmdir()
    r = install(src, target)
    assert r.returncode == 0, r.stderr
    assert (target / "skills/second-brain/SKILL.md").read_text() == "skill v2\n"
    assert (target / "commands/task.md").read_text() == "task v1\n"
    assert not (target / "commands/triage.md").exists()
    assert not (target / "skills/second-brain/reference").exists()
    entries = manifest_entries(target)
    files = manifest_files(target)
    assert "commands/task.md" in files
    assert "commands/triage.md" not in files


def test_rerun_is_idempotent(src, target):
    install(src, target)
    before = snapshot(target)
    assert install(src, target).returncode == 0
    assert snapshot(target) == before


def test_refuses_foreign_file_with_no_partial_install(src, target):
    (target / "commands").mkdir()
    (target / "commands/triage.md").write_text("mine\n")
    before = snapshot(target)
    r = install(src, target)
    assert r.returncode != 0
    assert "commands/triage.md" in r.stderr
    assert snapshot(target) == before  # nothing written, no manifest
    assert not (target / MANIFEST).exists()


def test_refuses_foreign_file_on_update(src, target):
    install(src, target)
    (src / "commands/task.md").write_text("task\n")
    (target / "commands/task.md").write_text("user's own task command\n")
    before = snapshot(target)
    (src / "skills/second-brain/SKILL.md").write_text("skill v2\n")
    r = install(src, target)
    assert r.returncode != 0
    assert snapshot(target) == before  # SKILL.md was not updated either


def test_refuses_file_where_directory_needed(src, target):
    (target / "skills").write_text("a file named skills\n")
    r = install(src, target)
    assert r.returncode != 0
    assert (target / "skills").read_text() == "a file named skills\n"


def test_uninstall_removes_exactly_manifest_files(src, target):
    (target / "commands").mkdir()
    (target / "commands/mine.md").write_text("mine\n")
    (target / "skills").mkdir()
    (target / "skills/other").mkdir()
    (target / "skills/other/SKILL.md").write_text("other\n")
    before = snapshot(target)
    install(src, target)
    r = run(src, "--uninstall", "--target", target)
    assert r.returncode == 0, r.stderr
    assert snapshot(target) == before


def test_uninstall_removes_dirs_it_created(src, target):
    install(src, target)
    assert run(src, "--uninstall", "--target", target).returncode == 0
    assert snapshot(target) == {}


def test_uninstall_keeps_user_file_added_inside_installed_dir(src, target):
    install(src, target)
    (target / "skills/second-brain/my-notes.md").write_text("keep me\n")
    r = run(src, "--uninstall", "--target", target)
    assert r.returncode == 0, r.stderr
    assert (target / "skills/second-brain/my-notes.md").read_text() == "keep me\n"
    assert not (target / "skills/second-brain/SKILL.md").exists()
    assert not (target / MANIFEST).exists()


def test_uninstall_without_manifest_fails_and_changes_nothing(src, target):
    (target / "commands").mkdir()
    (target / "commands/capture.md").write_text("mine\n")
    before = snapshot(target)
    r = run(src, "--uninstall", "--target", target)
    assert r.returncode != 0
    assert snapshot(target) == before


def test_uninstall_tolerates_already_missing_files(src, target):
    install(src, target)
    (target / "commands/capture.md").unlink()
    assert run(src, "--uninstall", "--target", target).returncode == 0
    assert snapshot(target) == {}


def test_never_touches_protected_files(src, target):
    (target / "CLAUDE.md").write_text("claude md\n")
    (target / "settings.json").write_text('{"a": 1}\n')
    (target / "docs").mkdir()
    (target / "docs/x.md").write_text("doc\n")
    protected = {k: v for k, v in snapshot(target).items()}
    install(src, target)
    install(src, target)
    run(src, "--uninstall", "--target", target)
    assert snapshot(target) == protected


def test_dry_run_install_writes_nothing(src, target):
    r = install(src, target, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "commands/capture.md" in r.stdout
    assert snapshot(target) == {}


def test_dry_run_does_not_create_missing_target(src, tmp_path):
    t = tmp_path / "absent"
    assert install(src, t, "--dry-run").returncode == 0
    assert not t.exists()


def test_dry_run_update_and_uninstall_write_nothing(src, target):
    install(src, target)
    (src / "skills/second-brain/SKILL.md").write_text("skill v2\n")
    before = snapshot(target)
    assert install(src, target, "--dry-run").returncode == 0
    assert run(src, "--uninstall", "--dry-run", "--target", target).returncode == 0
    assert snapshot(target) == before


def test_dry_run_still_reports_conflicts(src, target):
    (target / "commands").mkdir()
    (target / "commands/triage.md").write_text("mine\n")
    assert install(src, target, "--dry-run").returncode != 0


def test_default_target_is_home_dot_claude(src, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    r = run(src, home=home)
    assert r.returncode == 0, r.stderr
    assert (home / ".claude/commands/capture.md").exists()


# --- hostile filesystem ------------------------------------------------------


def test_refuses_symlink_in_source_skill(src, target, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("secret\n")
    (src / "skills/second-brain/leak.md").symlink_to(secret)
    r = install(src, target)
    assert r.returncode != 0
    assert snapshot(target) == {}


def test_refuses_symlink_in_source_commands(src, target, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("secret\n")
    (src / "commands/leak.md").symlink_to(secret)
    assert install(src, target).returncode != 0
    assert snapshot(target) == {}


def test_refuses_target_symlinked_skills_dir(src, target, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (target / "skills").symlink_to(outside)
    r = install(src, target)
    assert r.returncode != 0
    assert list(outside.iterdir()) == []


def test_refuses_target_symlinked_commands_dir(src, target, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (target / "commands").symlink_to(outside)
    assert install(src, target).returncode != 0
    assert list(outside.iterdir()) == []


def test_refuses_existing_symlink_at_destination_file(src, target, tmp_path):
    victim = tmp_path / "victim.md"
    victim.write_text("victim\n")
    (target / "commands").mkdir()
    (target / "commands/capture.md").symlink_to(victim)
    assert install(src, target).returncode != 0
    assert victim.read_text() == "victim\n"


def test_symlinked_target_directory_itself_is_allowed(src, tmp_path):
    real = tmp_path / "real-claude"
    real.mkdir()
    link = tmp_path / "linked-claude"
    link.symlink_to(real)
    assert install(src, link).returncode == 0
    assert (real / "commands/capture.md").exists()


def write_manifest(target, *entries, header=HEADER):
    (target / MANIFEST).write_text("\n".join([header, *entries]) + "\n")


def v2(entry):
    """'F path' -> 'F <hash> path' so a tampered entry fails for its path, not its shape."""
    return f"F {ZERO} {entry[2:]}" if entry.startswith("F ") else entry


@pytest.mark.parametrize(
    "bad",
    [
        "F ../outside.txt",
        "F commands/../../outside.txt",
        "F /etc/passwd",
        "F CLAUDE.md",
        "F settings.json",
        "F docs/x.md",
        "F commands/sub/x.md",
        "F skills/other/SKILL.md",
        "F skills/second-brain/../../CLAUDE.md",
        "D docs",
        "D .",
        "X commands/capture.md",
    ],
)
def test_tampered_manifest_is_rejected_on_uninstall(src, target, tmp_path, bad):
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n")
    (target / "CLAUDE.md").write_text("claude\n")
    (target / "settings.json").write_text("{}\n")
    (target / "docs").mkdir()
    (target / "docs/x.md").write_text("doc\n")
    install(src, target)
    entries = [*manifest_entries(target), v2(bad)]
    write_manifest(target, *entries)
    before = snapshot(target)
    r = run(src, "--uninstall", "--target", target)
    assert r.returncode != 0
    assert "outside the install area" in r.stderr or "bad manifest line" in r.stderr
    assert snapshot(target) == before  # nothing removed, validated up front
    assert outside.read_text() == "outside\n"


def test_tampered_manifest_is_rejected_on_install(src, target, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n")
    write_manifest(target, v2("F ../outside.txt"))
    assert install(src, target).returncode != 0
    assert outside.read_text() == "outside\n"
    assert not (target / "commands").exists()


def test_manifest_path_through_symlink_is_rejected(src, target, tmp_path):
    install(src, target)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text("outside\n")
    shutil.rmtree(target / "skills/second-brain/reference")
    (target / "skills/second-brain/reference").symlink_to(outside)
    r = run(src, "--uninstall", "--target", target)
    assert r.returncode != 0
    assert (outside / "SKILL.md").read_text() == "outside\n"


def test_manifest_symlink_is_rejected(src, target, tmp_path):
    real = tmp_path / "real-manifest"
    real.write_text(f"{HEADER}\nF commands/capture.md\n")
    (target / MANIFEST).symlink_to(real)
    assert run(src, "--uninstall", "--target", target).returncode != 0
    assert real.exists()


def test_uninstall_does_not_remove_directory_it_did_not_create(src, target):
    (target / "commands").mkdir()  # pre-existing, user-owned
    install(src, target)
    run(src, "--uninstall", "--target", target)
    assert (target / "commands").is_dir()
    assert not (target / "skills").exists()


def test_uninstall_does_not_remove_user_dir_even_if_manifest_lists_it(src, target):
    # A hand-edited manifest listing a user's non-empty installed-area dir only
    # triggers a non-recursive rmdir, so contents survive.
    (target / "skills/second-brain").mkdir(parents=True)
    (target / "skills/second-brain/mine.md").write_text("mine\n")
    write_manifest(target, "D skills", "D skills/second-brain")
    assert run(src, "--uninstall", "--target", target).returncode == 0
    assert (target / "skills/second-brain/mine.md").read_text() == "mine\n"


def test_target_path_with_spaces_and_odd_filenames(src, target):
    (src / "commands/my cmd.md").write_text("spaced\n")
    (src / "skills/second-brain/a b").mkdir()
    (src / "skills/second-brain/a b/c d.md").write_text("x\n")
    assert install(src, target).returncode == 0
    assert (target / "commands/my cmd.md").read_text() == "spaced\n"
    assert run(src, "--uninstall", "--target", target).returncode == 0
    assert snapshot(target) == {}


def test_source_missing_pieces_fails(src, target):
    shutil.rmtree(src / "commands")
    assert install(src, target).returncode != 0
    assert snapshot(target) == {}


def test_unknown_flag_and_missing_target_value_fail(src):
    assert run(src, "--bogus").returncode != 0
    assert run(src, "--target").returncode != 0


# --- source name validation --------------------------------------------------


def test_refuses_newline_in_source_directory_name(src, target, tmp_path):
    bad = src / "skills/second-brain" / "x\n../ESCAPED/deeper"
    try:
        bad.mkdir(parents=True)
    except OSError:
        pytest.skip("filesystem rejects newline in names")
    (bad / "f.md").write_text("x\n")
    r = install(src, target)
    assert r.returncode != 0
    assert "unsupported directory name" in r.stderr
    assert snapshot(target) == {}
    assert not (tmp_path / "ESCAPED").exists()
    assert not (target.parent / "ESCAPED").exists()


def test_refuses_newline_in_source_file_name(src, target):
    (src / "skills/second-brain" / "a\nF x.md").write_text("x\n")
    r = install(src, target)
    assert r.returncode != 0
    assert "unsupported file name" in r.stderr
    assert snapshot(target) == {}


def test_refuses_carriage_return_in_source_names(src, target):
    (src / "commands" / "a\rb.md").write_text("x\n")
    assert install(src, target).returncode != 0
    assert snapshot(target) == {}


def test_glob_component_symlink_in_target_is_not_followed(src, target, tmp_path):
    (src / "skills/second-brain/*").mkdir()
    (src / "skills/second-brain/*/f.md").write_text("x\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (target / "skills/second-brain").mkdir(parents=True)
    (target / "skills/second-brain/*").symlink_to(outside)
    r = install(src, target)
    assert r.returncode != 0
    assert list(outside.iterdir()) == []


# --- modified / replaced installed files ------------------------------------


def edit(target, rel="commands/capture.md"):
    (target / rel).write_text("user edit\n")


def test_manifest_records_sha256_of_installed_files(src, target):
    import hashlib

    install(src, target)
    line = next(e for e in manifest_entries(target) if e.endswith(" commands/capture.md"))
    assert line == "F " + hashlib.sha256(b"capture v1\n").hexdigest() + " commands/capture.md"


def test_modified_file_blocks_update_without_force(src, target):
    install(src, target)
    edit(target)
    (src / "commands/capture.md").write_text("capture v2\n")
    before = snapshot(target)
    r = install(src, target)
    assert r.returncode != 0
    assert "commands/capture.md" in r.stderr and "--force" in r.stderr
    assert snapshot(target) == before


def test_modified_file_overwritten_with_force(src, target):
    install(src, target)
    edit(target)
    assert install(src, target, "--force").returncode == 0
    assert (target / "commands/capture.md").read_text() == "capture v1\n"


def test_modified_file_blocks_uninstall_without_force(src, target):
    install(src, target)
    edit(target)
    before = snapshot(target)
    r = run(src, "--uninstall", "--target", target)
    assert r.returncode != 0 and "--force" in r.stderr
    assert snapshot(target) == before


def test_modified_file_removed_by_uninstall_with_force(src, target):
    install(src, target)
    edit(target)
    assert run(src, "--uninstall", "--force", "--target", target).returncode == 0
    assert snapshot(target) == {}


def test_modified_file_blocks_stale_removal_without_force(src, target):
    install(src, target)
    edit(target, "commands/triage.md")
    (src / "commands/triage.md").unlink()
    before = snapshot(target)
    r = install(src, target)
    assert r.returncode != 0 and "commands/triage.md" in r.stderr
    assert snapshot(target) == before
    assert install(src, target, "--force").returncode == 0
    assert not (target / "commands/triage.md").exists()


def test_installed_file_replaced_by_symlink(src, target, tmp_path):
    install(src, target)
    victim = tmp_path / "victim.md"
    victim.write_text("victim\n")
    (target / "commands/capture.md").unlink()
    (target / "commands/capture.md").symlink_to(victim)
    before = snapshot(target)
    for args in ([], ["--uninstall"]):
        r = run(src, *args, "--target", target)
        assert r.returncode != 0 and "symlink" in r.stderr
        assert snapshot(target) == before
    assert victim.read_text() == "victim\n"
    # --force replaces the link itself on install, never writing through it
    assert install(src, target, "--force").returncode == 0
    assert not (target / "commands/capture.md").is_symlink()
    assert (target / "commands/capture.md").read_text() == "capture v1\n"
    assert victim.read_text() == "victim\n"


def test_symlinked_installed_file_removed_by_forced_uninstall(src, target, tmp_path):
    install(src, target)
    victim = tmp_path / "victim.md"
    victim.write_text("victim\n")
    (target / "commands/capture.md").unlink()
    (target / "commands/capture.md").symlink_to(victim)
    assert run(src, "--uninstall", "--force", "--target", target).returncode == 0
    assert victim.read_text() == "victim\n"
    assert snapshot(target) == {}


def test_installed_file_replaced_by_directory(src, target):
    install(src, target)
    (target / "commands/capture.md").unlink()
    (target / "commands/capture.md").mkdir()
    before = snapshot(target)
    assert install(src, target).returncode != 0
    assert run(src, "--uninstall", "--target", target).returncode != 0
    assert snapshot(target) == before
    assert install(src, target, "--force").returncode == 0  # empty dir is replaced
    assert (target / "commands/capture.md").read_text() == "capture v1\n"


def test_force_never_deletes_non_empty_directory(src, target):
    install(src, target)
    (target / "commands/capture.md").unlink()
    (target / "commands/capture.md").mkdir()
    (target / "commands/capture.md/keep.txt").write_text("keep\n")
    before = snapshot(target)
    for args in ([], ["--uninstall"]):
        r = run(src, *args, "--force", "--target", target)
        assert r.returncode != 0
        assert snapshot(target) == before


def test_missing_installed_file_is_not_modified(src, target):
    install(src, target)
    (target / "commands/capture.md").unlink()
    assert install(src, target).returncode == 0
    assert (target / "commands/capture.md").exists()


def test_symlinked_parent_is_refused_even_with_force(src, target, tmp_path):
    install(src, target)
    outside = tmp_path / "outside"
    outside.mkdir()
    shutil.rmtree(target / "skills/second-brain/reference")
    (target / "skills/second-brain/reference").symlink_to(outside)
    for args in ([], ["--uninstall"]):
        assert run(src, *args, "--force", "--target", target).returncode != 0
    assert list(outside.iterdir()) == []


def test_user_file_at_path_listed_but_never_written_counts_as_modified(src, target):
    install(src, target)
    # an interrupted run listed a file it never wrote; the user then made their own
    (src / "commands/extra.md").write_text("extra v1\n")
    import hashlib

    h = hashlib.sha256(b"extra v1\n").hexdigest()
    with (target / MANIFEST).open("a") as fh:
        fh.write(f"F {h} commands/extra.md\n")
    (target / "commands/extra.md").write_text("the user's own file\n")
    r = install(src, target)
    assert r.returncode != 0 and "commands/extra.md" in r.stderr
    assert (target / "commands/extra.md").read_text() == "the user's own file\n"
    assert run(src, "--uninstall", "--target", target).returncode != 0


def test_half_updated_tree_after_interruption_is_not_mistaken_for_edits(src, target):
    install(src, target)
    (src / "commands/capture.md").write_text("capture v2\n")
    import hashlib

    # manifest as the pre-copy write leaves it (old hash), file already updated
    old = hashlib.sha256(b"capture v1\n").hexdigest()
    lines = [
        e if not e.endswith(" commands/capture.md") else f"F {old} commands/capture.md"
        for e in manifest_entries(target)
    ]
    write_manifest(target, *lines)
    (target / "commands/capture.md").write_text("capture v2\n")
    assert install(src, target).returncode == 0


# --- type changes in the source ----------------------------------------------


def test_path_changes_from_file_to_directory(src, target):
    (src / "skills/second-brain/thing").write_text("file\n")
    install(src, target)
    (src / "skills/second-brain/thing").unlink()
    (src / "skills/second-brain/thing").mkdir()
    (src / "skills/second-brain/thing/inner.md").write_text("inner\n")
    r = install(src, target)
    assert r.returncode == 0, r.stderr
    assert (target / "skills/second-brain/thing/inner.md").read_text() == "inner\n"
    assert "skills/second-brain/thing" in manifest_dirs(target)
    assert run(src, "--uninstall", "--target", target).returncode == 0
    assert snapshot(target) == {}


def test_path_changes_from_directory_to_file(src, target):
    (src / "skills/second-brain/thing").mkdir()
    (src / "skills/second-brain/thing/inner.md").write_text("inner\n")
    install(src, target)
    shutil.rmtree(src / "skills/second-brain/thing")
    (src / "skills/second-brain/thing").write_text("file\n")
    r = install(src, target)
    assert r.returncode == 0, r.stderr
    assert (target / "skills/second-brain/thing").read_text() == "file\n"
    assert run(src, "--uninstall", "--target", target).returncode == 0
    assert snapshot(target) == {}


def test_directory_to_file_refused_when_user_files_inside(src, target):
    (src / "skills/second-brain/thing").mkdir()
    (src / "skills/second-brain/thing/inner.md").write_text("inner\n")
    install(src, target)
    (target / "skills/second-brain/thing/mine.md").write_text("mine\n")
    shutil.rmtree(src / "skills/second-brain/thing")
    (src / "skills/second-brain/thing").write_text("file\n")
    before = snapshot(target)
    assert install(src, target).returncode != 0
    assert snapshot(target) == before


# --- path resolution ---------------------------------------------------------


def test_relative_target_with_leading_dash(src, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "-x").mkdir()
    r = run(src, "--target", "-x", cwd=work)
    assert r.returncode == 0, r.stderr
    assert (work / "-x/commands/capture.md").exists()


def test_relative_nonexistent_target_with_leading_dash(src, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    r = run(src, "--target", "-y", cwd=work)
    assert r.returncode == 0, r.stderr
    assert (work / "-y/commands/capture.md").exists()


def test_cdpath_does_not_redirect_target(src, tmp_path):
    work = tmp_path / "work"
    (work / "t").mkdir(parents=True)
    other = tmp_path / "other"
    (other / "t").mkdir(parents=True)
    r = run(src, "--target", "t", cwd=work, env={"CDPATH": f"{other}:."})
    assert r.returncode == 0, r.stderr
    assert (work / "t/commands/capture.md").exists()
    assert list((other / "t").iterdir()) == []


def test_refuses_root_as_target(src):
    for args in (["--target", "/"], ["--target", "/../.."], ["--uninstall", "--target", "/"]):
        r = run(src, *args, "--dry-run")
        assert r.returncode != 0
        assert "/" in r.stderr


@pytest.mark.parametrize("home", ["", "relative/home"])
def test_default_target_requires_absolute_home(src, tmp_path, home):
    r = run(src, home=home, cwd=tmp_path)
    assert r.returncode != 0
    assert "HOME" in r.stderr
    assert not (tmp_path / "relative").exists()
    assert not (tmp_path / ".claude").exists()


def test_target_that_is_a_file_fails(src, tmp_path):
    f = tmp_path / "afile"
    f.write_text("x\n")
    assert install(src, f).returncode != 0
    assert f.read_text() == "x\n"


def test_uninstall_nonexistent_target_fails_and_creates_nothing(src, tmp_path):
    t = tmp_path / "absent"
    assert run(src, "--uninstall", "--target", t).returncode != 0
    assert not t.exists()


# --- manifest edge cases -----------------------------------------------------


def test_uninstall_orders_directories_deepest_first(src, target):
    install(src, target)
    dirs = sorted(manifest_dirs(target))  # parents sort before children
    files = sorted(manifest_files(target))
    # child directories listed before their parents, so only sorting saves it
    write_manifest(target, *reversed([f"D {d}" for d in dirs]), *[f"F {ZERO} {f}" for f in files])
    for f in files:
        (target / f).unlink()
    assert run(src, "--uninstall", "--target", target).returncode == 0
    assert snapshot(target) == {}


@pytest.mark.parametrize("content", ["", "\n", "not a manifest\nF x\n", "# second-brain install manifest v9\n"])
def test_empty_or_unrecognised_manifest_header_is_rejected(src, target, content):
    (target / MANIFEST).write_text(content)
    (target / "commands").mkdir()
    (target / "commands/capture.md").write_text("mine\n")
    before = snapshot(target)
    assert run(src, "--uninstall", "--target", target).returncode != 0
    assert install(src, target).returncode != 0
    assert snapshot(target) == before


def test_tampered_manifest_rejected_under_dry_run(src, target, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n")
    write_manifest(target, v2("F ../outside.txt"))
    before = snapshot(target)
    assert run(src, "--uninstall", "--dry-run", "--target", target).returncode != 0
    assert install(src, target, "--dry-run").returncode != 0
    assert snapshot(target) == before


# --- failure partway through a copy ------------------------------------------


@pytest.mark.skipif(os.geteuid() == 0, reason="permissions are not enforced for root")
def test_copy_failure_midway_leaves_recoverable_state(src, target):
    # commands/ is user-owned and unwritable, so the skill copies and the commands do not
    (target / "commands").mkdir()
    (target / "commands").chmod(0o555)
    try:
        r = install(src, target)
        assert r.returncode != 0
        # manifest lists every file and directory, including ones never copied
        assert manifest_files(target) == {
            "skills/second-brain/SKILL.md",
            "skills/second-brain/reference/naming.md",
            "commands/capture.md",
            "commands/triage.md",
        }
        assert "skills/second-brain" in manifest_dirs(target)
        assert not (target / "commands/capture.md").exists()
        # no temporary files left behind anywhere
        leftovers = [p for p in target.rglob("*") if ".sbw-tmp." in p.name or p.name.startswith(MANIFEST + ".")]
        assert leftovers == []
    finally:
        (target / "commands").chmod(0o755)
    r = install(src, target)
    assert r.returncode == 0, r.stderr
    assert (target / "commands/capture.md").exists()
    assert run(src, "--uninstall", "--target", target).returncode == 0
    # only the user's own, pre-existing commands/ directory remains
    assert snapshot(target) == {"commands": ("dir", None)}


def test_help_prints_header_comment(src):
    r = run(src, "--help")
    assert r.returncode == 0
    assert "--uninstall" in r.stdout and "manifest" in r.stdout
    assert "set -euo" not in r.stdout


def test_failed_cp_cleans_up_temp_files_and_keeps_manifest(src, target, tmp_path):
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "cp").write_text("#!/bin/sh\nexit 1\n")
    (shim / "cp").chmod(0o755)
    r = install_with_path(src, target, f"{shim}:{os.environ['PATH']}")
    assert r.returncode != 0
    leftovers = [p for p in target.rglob("*") if ".sbw-tmp." in p.name or p.name.startswith(MANIFEST + ".")]
    assert leftovers == []
    assert len(manifest_files(target)) == 4
    assert install(src, target).returncode == 0
    assert run(src, "--uninstall", "--target", target).returncode == 0
    assert snapshot(target) == {}


def install_with_path(src, target, path):
    return run(src, "--target", target, env={"PATH": path})


def test_v1_manifest_header_is_refused(src, target):
    install(src, target)
    files = sorted(manifest_files(target))
    write_manifest(target, *[f"F {f}" for f in files], header=HEADER_V1)
    before = snapshot(target)
    for args in ([], ["--uninstall"], ["--force"], ["--uninstall", "--force"]):
        r = run(src, *args, "--target", target)
        assert r.returncode != 0 and "unrecognised manifest header" in r.stderr
    assert snapshot(target) == before


def test_backslash_in_source_name_round_trips(src, target):
    (src / "commands" / "a\\b.md").write_text("backslash\n")
    assert install(src, target).returncode == 0
    assert (target / "commands" / "a\\b.md").read_text() == "backslash\n"
    assert "commands/a\\b.md" in manifest_files(target)
    assert install(src, target).returncode == 0
    assert run(src, "--uninstall", "--target", target).returncode == 0
    assert snapshot(target) == {}


def test_refuses_control_character_in_source_name(src, target):
    (src / "commands" / "a\x1bb.md").write_text("x\n")
    r = install(src, target)
    assert r.returncode != 0 and "unsupported file name" in r.stderr
    assert snapshot(target) == {}


def test_update_interrupted_before_a_later_file_is_replaced(src, target, tmp_path):
    """Files not yet replaced still hold old content; the interim manifest must still accept them."""
    install(src, target)
    for rel in ("skills/second-brain/SKILL.md", "skills/second-brain/reference/naming.md",
                "commands/capture.md", "commands/triage.md"):
        (src / rel).write_text("v2 of " + rel + "\n")
    shim = tmp_path / "shim"
    shim.mkdir()
    counter = tmp_path / "count"
    (shim / "cp").write_text(
        "#!/bin/sh\n"
        f"n=$(cat '{counter}' 2>/dev/null || echo 0); n=$((n+1)); echo $n > '{counter}'\n"
        '[ "$n" -ne 3 ] || exit 1\n'
        'exec /bin/cp "$@"\n'
    )
    (shim / "cp").chmod(0o755)
    r = install_with_path(src, target, f"{shim}:{os.environ['PATH']}")
    assert r.returncode != 0
    contents = {rel: (target / rel).read_text() for rel in manifest_files(target)}
    assert sum(c.startswith("v2") for c in contents.values()) == 2  # two replaced, two still old
    # uninstall refuses and says why
    u = run(src, "--uninstall", "--target", target)
    assert u.returncode != 0 and "interrupted update" in u.stderr
    # re-run (cp is real again) succeeds without --force and reports nothing as modified
    r = install(src, target)
    assert r.returncode == 0, r.stderr
    assert "modified" not in r.stderr and "Installed files differ" not in r.stderr
    assert all((target / rel).read_text() == "v2 of " + rel + "\n" for rel in contents)


def test_help_mentions_interrupted_update_and_hides_lint_directive(src):
    r = run(src, "--help")
    assert "interrupted update" in r.stdout
    assert "shellcheck" not in r.stdout


def add_debris(src):
    scripts = src / "skills/second-brain/scripts"
    (scripts / "__pycache__").mkdir(parents=True, exist_ok=True)
    (scripts / "vault_git.py").write_text("# dummy\n")
    (scripts / "__pycache__" / "x.cpython-312.pyc").write_bytes(b"\x00bytecode")
    (scripts / "__pycache__" / "y.pyo").write_bytes(b"\x00bytecode")
    (src / "skills/second-brain/y.pyc").write_bytes(b"\x00bytecode")
    (src / "skills/second-brain/.DS_Store").write_bytes(b"\x00debris")
    (src / "skills/second-brain/reference/.DS_Store").write_bytes(b"\x00debris")


def test_skips_bytecode_caches_and_os_debris(src, target):
    add_debris(src)
    r = install(src, target)
    assert r.returncode == 0, r.stderr
    assert (target / "skills/second-brain/scripts/vault_git.py").read_text() == "# dummy\n"
    assert not (target / "skills/second-brain/scripts/__pycache__").exists()
    assert not (target / "skills/second-brain/y.pyc").exists()
    assert not (target / "skills/second-brain/.DS_Store").exists()
    assert not (target / "skills/second-brain/reference/.DS_Store").exists()
    manifest = (target / MANIFEST).read_text()
    for needle in ("__pycache__", ".pyc", ".pyo", ".DS_Store"):
        assert needle not in manifest
    assert "skills/second-brain/scripts/vault_git.py" in manifest_files(target)
    assert "skills/second-brain/scripts" in manifest_dirs(target)


def test_other_dotfiles_still_ship(src, target):
    add_debris(src)
    (src / "skills/second-brain/.keep").write_text("kept\n")
    assert install(src, target).returncode == 0
    assert (target / "skills/second-brain/.keep").read_text() == "kept\n"


def test_dry_run_does_not_list_skipped_entries(src, target):
    add_debris(src)
    r = install(src, target, "--dry-run")
    assert r.returncode == 0, r.stderr
    for needle in ("__pycache__", ".pyc", ".pyo", ".DS_Store"):
        assert needle not in r.stdout
    assert "scripts/vault_git.py" in r.stdout


def test_previously_installed_bytecode_is_removed_as_stale(src, target):
    (src / "skills/second-brain/scripts").mkdir()
    (src / "skills/second-brain/scripts/vault_git.py").write_text("# dummy\n")
    assert install(src, target).returncode == 0
    add_debris(src)
    # simulate an earlier install that shipped a cache: file, directory and manifest entries
    import hashlib
    extra = {
        "skills/second-brain/scripts/__pycache__/x.cpython-312.pyc": b"old bytecode",
        "skills/second-brain/y.pyc": b"old pyc",
    }
    lines = [(target / MANIFEST).read_text().rstrip("\n")]
    lines.append("D skills/second-brain/scripts/__pycache__")
    (target / "skills/second-brain/scripts/__pycache__").mkdir()
    for rel, data in extra.items():
        (target / rel).write_bytes(data)
        lines.append(f"F {hashlib.sha256(data).hexdigest()} {rel}")
    (target / MANIFEST).write_text("\n".join(lines) + "\n")
    r = install(src, target)
    assert r.returncode == 0, r.stderr
    assert not (target / "skills/second-brain/scripts/__pycache__").exists()
    assert not (target / "skills/second-brain/y.pyc").exists()
    assert (target / "skills/second-brain/scripts/vault_git.py").exists()
    assert "__pycache__" not in (target / MANIFEST).read_text()
    assert ".pyc" not in (target / MANIFEST).read_text()


def test_uninstall_is_clean_with_skipped_entries_in_source(src, target):
    add_debris(src)
    assert install(src, target).returncode == 0
    r = run(src, "--uninstall", "--target", target)
    assert r.returncode == 0, r.stderr
    assert snapshot(target) == {}


def test_directory_with_junk_name_is_not_skipped(src, target):
    d = src / "skills/second-brain/x.pyc"
    d.mkdir()
    (d / "notes.md").write_text("real\n")
    r = install(src, target)
    assert r.returncode == 0, r.stderr
    assert (target / "skills/second-brain/x.pyc/notes.md").read_text() == "real\n"
    assert "skills/second-brain/x.pyc/notes.md" in manifest_files(target)


def test_symlink_with_junk_name_is_refused(src, target, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n")
    (src / "skills/second-brain/leak.pyc").symlink_to(outside)
    r = install(src, target)
    assert r.returncode != 0
    assert "symlinks or special files" in r.stderr
    assert not (target / MANIFEST).exists()


def test_regular_junk_files_and_real_pycache_dir_still_skipped(src, target):
    (src / "skills/second-brain/y.pyc").write_bytes(b"\x00")
    (src / "skills/second-brain/__pycache__").mkdir()
    (src / "skills/second-brain/__pycache__/z.pyc").write_bytes(b"\x00")
    r = install(src, target)
    assert r.returncode == 0, r.stderr
    assert not (target / "skills/second-brain/y.pyc").exists()
    assert not (target / "skills/second-brain/__pycache__").exists()
