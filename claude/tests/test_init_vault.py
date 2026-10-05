"""Tests for claude/scripts/init_vault.py (plan P1-04, sections 2.6 and 2.9)."""

import importlib.util
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "claude" / "scripts" / "init_vault.py"
SEED = REPO / "claude" / "skills" / "second-brain"
TEMPLATE_NAMES = ["task", "project", "daily", "decision", "lesson", "capture"]
# The only place the real old vault location is named (see the guarded test).
REAL_OLD_VAULT = "/mnt/c/Users/User/Documents/Obsidian Vault"

PHASE1_DIRS = {
    "00-Inbox",
    "01-Daily",
    "01-Daily/2026",
    "02-Work",
    "02-Work/Projects",
    "02-Work/Tasks",
    "05-Knowledge",
    "05-Knowledge/Decisions",
    "05-Knowledge/Lessons",
    "08-System",
    "08-System/Templates",
}


def _load():
    spec = importlib.util.spec_from_file_location("init_vault", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def git_env(tmp_path_factory, monkeypatch):
    """Isolate git from this machine's configuration; a global identity is set."""
    home = tmp_path_factory.mktemp("home")
    gitconfig = home / "gitconfig"
    gitconfig.write_text(
        "[user]\n\tname = Test User\n\temail = test@example.com\n"
        "[core]\n\tautocrlf = true\n\tfilemode = true\n"
    )
    for var in [v for v in os.environ if v.startswith("GIT_")]:
        monkeypatch.delenv(var)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setattr(os, "geteuid", lambda: 1000)  # the script refuses root
    return gitconfig


@pytest.fixture
def init_vault():
    return _load()


def clean_env():
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")} | {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }


def git(target, *args):
    return subprocess.run(
        ["git", *args], cwd=target, capture_output=True, text=True, check=True,
        env=clean_env(),
    ).stdout


def all_dirs(root):
    return {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_dir() and ".git" not in p.relative_to(root).parts
    }


def snapshot(root, skip=None):
    return sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if skip is None or skip not in p.parents and p != skip
    )


def forbid_fs_access(monkeypatch, *prefixes):
    """Make any filesystem call on a path at or under a prefix fail the test."""
    prefixes = [p.casefold() for p in prefixes]

    def guard(original):
        def wrapper(path, *args, **kwargs):
            if isinstance(path, (str, bytes, os.PathLike)):
                text = os.fsdecode(path).casefold()
                if any(text == p or text.startswith(p + "/") for p in prefixes):
                    raise AssertionError(f"filesystem access to forbidden path: {path}")
            return original(path, *args, **kwargs)

        return wrapper

    for owner, name in [
        (os, "stat"), (os, "lstat"), (os, "listdir"), (os, "scandir"),
        (os, "mkdir"), (os, "access"), (os.path, "realpath"), (Path, "resolve"),
    ]:
        monkeypatch.setattr(owner, name, guard(getattr(owner, name)))


# ---------------------------------------------------------------- the vault


def test_creates_exactly_the_phase1_folders(git_env, init_vault, tmp_path):
    target = tmp_path / "Second Brain"
    assert init_vault.main([str(target)]) == 0
    assert all_dirs(target) == PHASE1_DIRS


def test_templates_are_byte_identical(git_env, init_vault, tmp_path):
    target = tmp_path / "v"
    init_vault.main([str(target)])
    dest = target / "08-System" / "Templates"
    assert sorted(p.name for p in dest.iterdir()) == sorted(
        f"{n}.md" for n in TEMPLATE_NAMES
    )
    for name in TEMPLATE_NAMES:
        assert (dest / f"{name}.md").read_bytes() == (
            SEED / "templates" / f"{name}.md"
        ).read_bytes()


def test_readme_and_ignore_files(git_env, init_vault, tmp_path):
    target = tmp_path / "v"
    init_vault.main([str(target)])
    assert (target / "README.md").read_bytes() == (SEED / "vault-readme.md").read_bytes()
    assert (target / ".gitattributes").read_bytes() == b"* -text\n"
    ignore = (target / ".gitignore").read_text().splitlines()
    assert ignore == [
        ".obsidian/workspace*.json",
        ".obsidian/cache/",
        ".trash/",
        ".*.sbw-tmp-*",
        ".DS_Store",
        "Thumbs.db",
        "desktop.ini",
    ]
    sbignore = (target / ".sbignore").read_text().splitlines()
    assert sbignore and all(line.startswith("#") for line in sbignore)


def test_git_local_config(git_env, init_vault, tmp_path):
    target = tmp_path / "v"
    init_vault.main([str(target)])
    local = git(target, "config", "--local", "--list")
    entries = dict(line.split("=", 1) for line in local.splitlines())
    assert entries["core.autocrlf"] == "false"
    assert entries["core.filemode"] == "false"
    assert entries["core.quotepath"] == "false"
    assert entries["user.name"] == "Test User"
    assert entries["user.email"] == "test@example.com"
    assert git(target, "symbolic-ref", "--short", "HEAD").strip() == "main"


def test_one_initial_commit_clean_tree_no_remote(git_env, init_vault, tmp_path):
    target = tmp_path / "v"
    init_vault.main([str(target)])
    assert len(git(target, "log", "--format=%H").split()) == 1
    assert git(target, "log", "-1", "--format=%an <%ae>").strip() == (
        "Test User <test@example.com>"
    )
    assert git(target, "status", "--porcelain") == ""
    assert git(target, "remote").strip() == ""
    tracked = set(git(target, "ls-files").split("\n")) - {""}
    assert {"README.md", ".gitignore", ".gitattributes", ".sbignore"} <= tracked
    assert "08-System/Templates/task.md" in tracked


def test_path_with_spaces_and_missing_parents(git_env, init_vault, tmp_path):
    target = tmp_path / "a b" / "Second Brain"
    assert init_vault.main([str(target)]) == 0
    assert (target / ".git").is_dir()


def test_accepts_existing_empty_directory(git_env, init_vault, tmp_path):
    target = tmp_path / "v"
    target.mkdir()
    assert init_vault.main([str(target)]) == 0


def test_writes_nothing_outside_the_target(git_env, init_vault, tmp_path):
    (tmp_path / "sibling").mkdir()
    (tmp_path / "sibling" / "keep.txt").write_text("x")
    home = Path(os.environ["HOME"])
    target = tmp_path / "v"
    before = (snapshot(tmp_path, target), snapshot(home))
    assert init_vault.main([str(target)]) == 0
    assert (snapshot(tmp_path, target), snapshot(home)) == before


# ------------------------------------------------------ refusals: the target


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("name", ["note.md", ".hidden", ".git"])
def test_refuses_non_empty_target(git_env, init_vault, tmp_path, name, dry_run, capsys):
    target = tmp_path / "v"
    target.mkdir()
    (target / name).write_text("x")
    before = snapshot(target)
    assert init_vault.main([str(target), *(["--dry-run"] if dry_run else [])]) != 0
    assert snapshot(target) == before
    captured = capsys.readouterr()
    assert "not empty" in captured.err
    assert "dry run" not in captured.out


def test_refuses_file_target(git_env, init_vault, tmp_path):
    target = tmp_path / "f"
    target.write_text("x")
    assert init_vault.main([str(target)]) != 0
    assert target.read_text() == "x"


def test_refuses_symlink_target(git_env, init_vault, tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    assert init_vault.main([str(link)]) != 0
    assert list(real.iterdir()) == []


def test_refuses_empty_string_target(git_env, init_vault, capsys):
    assert init_vault.main([""]) != 0
    assert "empty" in capsys.readouterr().err


def test_refuses_dotdot_component(git_env, init_vault, tmp_path, capsys):
    (tmp_path / "a").mkdir()
    assert init_vault.main([str(tmp_path / "a" / ".." / "v")]) != 0
    assert ".." in capsys.readouterr().err
    assert not (tmp_path / "v").exists()


def test_refuses_root(git_env, init_vault, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    assert init_vault.main([str(tmp_path / "v")]) != 0
    assert "root" in capsys.readouterr().err
    assert not (tmp_path / "v").exists()


def test_refuses_git_under_mnt(git_env, init_vault, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(shutil, "which", lambda name: "/mnt/z/nowhere/git.exe")
    assert init_vault.main([str(tmp_path / "v")]) != 0
    assert "refusing a git under /mnt" in capsys.readouterr().err
    assert not (tmp_path / "v").exists()


def test_uses_the_git_path_it_found(git_env, init_vault, tmp_path, monkeypatch):
    log = tmp_path / "shim.log"
    shim = tmp_path / "shim-git"
    shim.write_text(f'#!/bin/sh\necho x >> "{log}"\nexec {shutil.which("git")} "$@"\n')
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr(shutil, "which", lambda name: str(shim))
    assert init_vault.main([str(tmp_path / "v")]) == 0
    # one read of user.name, one of user.email, then every repository command
    assert len(log.read_text().splitlines()) >= 8


# ------------------------------------------------- refusals: old vault, C:


@pytest.fixture
def old_vault(init_vault, tmp_path, monkeypatch):
    """Stand-in for the old vault; the real location is never touched."""
    stand_in = tmp_path / "mnt" / "Documents" / "Obsidian Vault"
    monkeypatch.setattr(init_vault, "OLD_VAULT", str(stand_in))
    return stand_in


def test_old_vault_constant_is_the_real_path(init_vault):
    assert init_vault.OLD_VAULT == REAL_OLD_VAULT


@pytest.mark.parametrize(
    "build",
    [
        lambda v: str(v),
        lambda v: str(v) + "/",
        lambda v: str(v / "00-Inbox" / "new"),
        lambda v: str(v) + "/../Obsidian Vault/x",
        lambda v: str(v.parent / "Foo" / ".." / "Obsidian Vault"),
        lambda v: str(v).swapcase() + "/sub",
    ],
)
def test_refuses_old_vault_paths(git_env, init_vault, old_vault, build, capsys):
    assert init_vault.main([build(old_vault)]) != 0
    assert "old vault" in capsys.readouterr().err
    assert not old_vault.exists()


def test_refuses_old_vault_through_symlink(git_env, init_vault, old_vault, tmp_path):
    old_vault.mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(old_vault)
    assert init_vault.main([str(link / "new")]) != 0
    assert list(old_vault.iterdir()) == []


def test_refuses_relative_path_into_old_vault(git_env, init_vault, old_vault, monkeypatch):
    old_vault.mkdir(parents=True)
    monkeypatch.chdir(old_vault.parent)
    assert init_vault.main(["Obsidian Vault/new"]) != 0
    assert list(old_vault.iterdir()) == []


def test_dotdot_out_of_old_vault_refused_before_any_stat(
    git_env, init_vault, old_vault, monkeypatch, capsys
):
    forbid_fs_access(monkeypatch, str(old_vault))
    assert init_vault.main([str(old_vault) + "/../Elsewhere"]) != 0
    assert ".." in capsys.readouterr().err


def test_real_old_vault_and_c_drive_refused_without_filesystem_access(
    git_env, init_vault, monkeypatch, capsys
):
    forbid_fs_access(monkeypatch, "/mnt/c", "/mnt/d/progra~1")
    cases = [
        (REAL_OLD_VAULT, "old vault"),
        (REAL_OLD_VAULT + "/00-Inbox/new", "old vault"),
        ("/mnt/c", "drive C"),
        ("/MNT/C/Users/User/DOCUME~1/x", "drive C"),
        ("/mnt/c/Users/anyone/vault", "drive C"),
        ("/mnt/d/PROGRA~1/vault", "short-name"),
    ]
    for path, message in cases:
        assert init_vault.main([path]) != 0, path
        assert message in capsys.readouterr().err, path


@pytest.mark.parametrize("part", ["DOCUME~1", "a~2b", "~1"])
def test_refuses_short_name_component(git_env, init_vault, tmp_path, part, capsys):
    assert init_vault.main([str(tmp_path / part / "v")]) != 0
    assert "short-name" in capsys.readouterr().err
    assert not (tmp_path / part).exists()


def _mountinfo(mount: Path, line_tail: str, *extra: str) -> str:
    escaped = str(mount).replace(" ", "\\040")
    lines = [
        "20 1 8:1 / / rw - ext4 /dev/sda1 rw",
        f"100 20 0:50 / {escaped} rw - {line_tail}",
        *extra,
    ]
    return "\n".join(lines) + "\n"


C_TAIL = r"9p C:\134 rw,dirsync,aname=drvfs;path=C:\;uid=1000"
D_TAIL = r"9p D:\134 rw,dirsync,aname=drvfs;path=D:\;uid=1000"


def test_refuses_other_mount_point_of_drive_c(git_env, init_vault, tmp_path, monkeypatch, capsys):
    mount = tmp_path / "my mount"
    mount.mkdir()
    monkeypatch.setattr(init_vault, "_read_mountinfo", lambda: _mountinfo(mount, C_TAIL))
    assert init_vault.main([str(mount / "sub" / "v")]) != 0
    assert "drive C" in capsys.readouterr().err
    assert list(mount.iterdir()) == []


def test_refuses_old_style_drvfs_mount_of_c(git_env, init_vault, tmp_path, monkeypatch):
    monkeypatch.setattr(
        init_vault, "_read_mountinfo", lambda: _mountinfo(tmp_path, r"drvfs C:\134 rw")
    )
    assert init_vault.main([str(tmp_path / "v")]) != 0


def test_accepts_mount_of_drive_d(git_env, init_vault, tmp_path, monkeypatch):
    mount = tmp_path / "my mount"
    mount.mkdir()
    monkeypatch.setattr(init_vault, "_read_mountinfo", lambda: _mountinfo(mount, D_TAIL))
    assert init_vault.main([str(mount / "v")]) == 0


def test_longest_mount_wins(git_env, init_vault, tmp_path, monkeypatch):
    inner = tmp_path / "inner"
    inner.mkdir()
    text = _mountinfo(tmp_path, C_TAIL, f"101 100 0:51 / {inner} rw - ext4 /dev/sdb rw")
    monkeypatch.setattr(init_vault, "_read_mountinfo", lambda: text)
    assert init_vault.main([str(inner / "v")]) == 0
    assert init_vault.main([str(tmp_path / "other")]) != 0


def test_unreadable_mountinfo_refuses(git_env, init_vault, tmp_path, monkeypatch):
    def broken():
        raise OSError("no /proc")

    monkeypatch.setattr(init_vault, "_read_mountinfo", broken)
    assert init_vault.main([str(tmp_path / "v")]) != 0
    assert not (tmp_path / "v").exists()


# --------------------------------------------------- refusals: git identity


def test_refuses_without_global_email(git_env, init_vault, tmp_path, capsys):
    git_env.write_text("[user]\n\tname = Test User\n")
    target = tmp_path / "v"
    assert init_vault.main([str(target)]) != 0
    assert not target.exists()
    assert "user.email" in capsys.readouterr().err


def test_refuses_without_global_name(git_env, init_vault, tmp_path):
    git_env.write_text("[user]\n\temail = a@b.c\n")
    target = tmp_path / "v"
    assert init_vault.main([str(target)]) != 0
    assert not target.exists()


# ------------------------------------------------------------------ dry run


def test_dry_run_writes_nothing(git_env, init_vault, tmp_path, capsys):
    target = tmp_path / "v"
    assert init_vault.main([str(target), "--dry-run"]) == 0
    assert not target.exists()
    out = capsys.readouterr().out
    assert "08-System/Templates" in out and "git init" in out
    # the plan must name everything create() makes
    for folder in PHASE1_DIRS:
        if not any(d.startswith(folder + "/") for d in PHASE1_DIRS):  # leaf folders
            assert f"mkdir  {folder}/" in out
    for name in TEMPLATE_NAMES:
        assert f"08-System/Templates/{name}.md" in out
    for name in ("README.md", ".gitignore", ".gitattributes", ".sbignore"):
        assert name in out


def test_dry_run_into_empty_dir_leaves_it_empty(git_env, init_vault, tmp_path):
    target = tmp_path / "v"
    target.mkdir()
    assert init_vault.main([str(target), "--dry-run"]) == 0
    assert list(target.iterdir()) == []


def test_dry_run_still_refuses(git_env, init_vault, old_vault, tmp_path):
    assert init_vault.main([str(old_vault), "--dry-run"]) != 0
    git_env.write_text("")
    assert init_vault.main([str(tmp_path / "v"), "--dry-run"]) != 0


# --------------------------------------------------------- git isolation


def _marker_script(path: Path, marker: Path) -> Path:
    path.write_text(f"#!/bin/sh\necho ran >> {marker}\nexit 1\n")
    path.chmod(0o755)
    return path


def test_global_hooks_fsmonitor_templates_and_ignores_do_not_apply(
    git_env, init_vault, tmp_path
):
    marker = tmp_path / "MARKER"
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    for hook in ("pre-commit", "post-commit", "post-index-change", "commit-msg",
                 "reference-transaction", "post-checkout", "pre-push"):
        _marker_script(hooks / hook, marker)
    fsmon = _marker_script(tmp_path / "fsmonitor", marker)
    template = tmp_path / "template"
    (template / "hooks").mkdir(parents=True)
    _marker_script(template / "hooks" / "pre-commit", marker)
    (template / "from-template.txt").write_text("x")
    excludes = tmp_path / "excludes"
    excludes.write_text("*.md\n")
    with open(git_env, "a") as fh:
        fh.write(
            f"[core]\n\thooksPath = {hooks}\n\tfsmonitor = {fsmon}\n"
            f"\texcludesFile = {excludes}\n[init]\n\ttemplateDir = {template}\n"
        )
    target = tmp_path / "v"
    assert init_vault.main([str(target)]) == 0
    assert not marker.exists()
    assert not (target / ".git" / "from-template.txt").exists()
    assert not (target / ".git" / "hooks" / "pre-commit").exists()
    assert "README.md" in git(target, "ls-files").split("\n")


def test_git_config_count_injection_has_no_effect(git_env, init_vault, tmp_path, monkeypatch):
    marker = tmp_path / "MARKER"
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    for hook in ("pre-commit", "post-commit", "post-index-change"):
        _marker_script(hooks / hook, marker)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "secret.txt").write_text("x")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.hooksPath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(hooks))
    monkeypatch.setenv("GIT_CONFIG_KEY_1", "core.worktree")
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", str(foreign))
    target = tmp_path / "v"
    assert init_vault.main([str(target)]) == 0
    assert not marker.exists()
    assert "secret.txt" not in git(target, "ls-files")
    assert "README.md" in git(target, "ls-files")
    assert sorted(p.name for p in foreign.iterdir()) == ["secret.txt"]


def test_git_author_variables_do_not_change_the_commit(git_env, init_vault, tmp_path, monkeypatch):
    for var, value in [("GIT_AUTHOR_NAME", "Evil"), ("GIT_AUTHOR_EMAIL", "evil@x"),
                       ("GIT_COMMITTER_NAME", "Evil"), ("GIT_COMMITTER_EMAIL", "evil@x")]:
        monkeypatch.setenv(var, value)
    target = tmp_path / "v"
    assert init_vault.main([str(target)]) == 0
    assert git(target, "log", "-1", "--format=%an <%ae> %cn <%ce>").strip() == (
        "Test User <test@example.com> Test User <test@example.com>"
    )


def test_git_trace_writes_nothing(git_env, init_vault, tmp_path, monkeypatch):
    traces = [tmp_path / f"trace-{n}" for n in ("a", "b", "c")]
    for var, path in zip(("GIT_TRACE", "GIT_TRACE_SETUP", "GIT_TRACE_PERFORMANCE"), traces):
        monkeypatch.setenv(var, str(path))
    assert init_vault.main([str(tmp_path / "v")]) == 0
    assert not any(t.exists() for t in traces)


def test_every_repository_command_is_isolated(git_env, init_vault, tmp_path, monkeypatch):
    calls = []
    real_run = subprocess.run

    def spy(cmd, *args, **kwargs):
        calls.append((cmd, kwargs.get("env")))
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(init_vault.subprocess, "run", spy)
    assert init_vault.main([str(tmp_path / "v")]) == 0
    repo_calls = [c for c in calls if "--global" not in c[0]]
    # git, five "-c k=v" pairs, then the subcommand
    subcommands = {c[0][11] for c in repo_calls}
    assert {"init", "config", "remote", "add", "commit"} <= subcommands
    assert len(repo_calls) >= 8
    for cmd, env in repo_calls:
        for override in ("core.hooksPath=/dev/null", "core.fsmonitor=false",
                         "core.attributesFile=/dev/null", "core.excludesFile=/dev/null"):
            assert override in cmd
        assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"
        assert env["GIT_CONFIG_NOSYSTEM"] == "1"
        assert not [
            k for k in env
            if k.startswith("GIT_") and k not in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM",
                                                  "GIT_CEILING_DIRECTORIES")
        ]
        assert env["GIT_CEILING_DIRECTORIES"] == str(tmp_path)


def test_refuses_when_the_new_repository_has_a_remote(git_env, init_vault, tmp_path, monkeypatch, capsys):
    real = init_vault._run_git

    def with_remote(git, target, args):
        return "origin\n" if args == ["remote"] else real(git, target, args)

    monkeypatch.setattr(init_vault, "_run_git", with_remote)
    assert init_vault.main([str(tmp_path / "v")]) != 0
    err = capsys.readouterr().err
    assert "remote" in err and "partial vault left" in err


def test_ignores_hostile_git_dir(git_env, init_vault, tmp_path, monkeypatch):
    other = tmp_path / "other"
    other.mkdir()
    subprocess.run(["git", "init", "-q", str(other)], check=True, env=clean_env())
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    target = tmp_path / "v"
    assert init_vault.main([str(target)]) == 0
    assert (target / ".git").is_dir()
    assert subprocess.run(
        ["git", "-C", str(other), "rev-parse", "--verify", "HEAD"],
        capture_output=True, env=clean_env(),
    ).returncode != 0


# ---------------------------------------- check-then-write and failures


def _swap_after_check(monkeypatch, init_vault, swap):
    real_check = init_vault.check

    def check(raw):
        plan = real_check(raw)
        swap(plan.target)
        return plan

    monkeypatch.setattr(init_vault, "check", check)


def test_target_swapped_for_symlink_after_check_existing_dir(
    git_env, init_vault, tmp_path, monkeypatch, capsys
):
    target, elsewhere = tmp_path / "v", tmp_path / "elsewhere"
    target.mkdir()
    elsewhere.mkdir()

    def swap(path):
        path.rmdir()
        path.symlink_to(elsewhere)

    _swap_after_check(monkeypatch, init_vault, swap)
    assert init_vault.main([str(target)]) != 0
    assert list(elsewhere.iterdir()) == []
    assert "changed" in capsys.readouterr().err


def test_target_swapped_for_symlink_after_check_new_dir(
    git_env, init_vault, tmp_path, monkeypatch
):
    target, elsewhere = tmp_path / "v", tmp_path / "elsewhere"
    elsewhere.mkdir()
    _swap_after_check(monkeypatch, init_vault, lambda p: p.symlink_to(elsewhere))
    assert init_vault.main([str(target)]) != 0
    assert list(elsewhere.iterdir()) == []


def test_target_swapped_before_git_steps(git_env, init_vault, tmp_path, monkeypatch, capsys):
    target, elsewhere = tmp_path / "v", tmp_path / "elsewhere"
    elsewhere.mkdir()
    real_write = init_vault._write_new

    def write(path, data):
        real_write(path, data)
        if path.name == ".sbignore":  # the last write before the git steps
            target.rename(tmp_path / "moved")
            target.symlink_to(elsewhere)

    monkeypatch.setattr(init_vault, "_write_new", write)
    assert init_vault.main([str(target)]) != 0
    assert list(elsewhere.iterdir()) == []
    assert "changed" in capsys.readouterr().err


def test_target_swapped_between_git_calls(git_env, init_vault, tmp_path, monkeypatch, capsys):
    target, elsewhere = tmp_path / "v", tmp_path / "elsewhere"
    elsewhere.mkdir()
    real = init_vault._run_git

    def run(git, tgt, args):
        out = real(git, tgt, args)
        if args[0] == "init":  # swap right after git init
            target.rename(tmp_path / "moved")
            target.symlink_to(elsewhere)
        return out

    monkeypatch.setattr(init_vault, "_run_git", run)
    assert init_vault.main([str(target)]) != 0
    assert list(elsewhere.iterdir()) == []
    assert "changed" in capsys.readouterr().err


def _parent_repo_state(parent):
    return (
        (parent / ".git" / "config").read_bytes(),
        (parent / ".git" / "index").read_bytes(),
        git(parent, "log", "--format=%H %s"),
        git(parent, "config", "--local", "--list"),
    )


def _make_parent_repo(tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    git(parent, "init", "-q", "-b", "main")
    git(parent, "config", "user.name", "P")
    git(parent, "config", "user.email", "p@x")
    (parent / "f.txt").write_text("x")
    git(parent, "add", "f.txt")
    git(parent, "commit", "-q", "-m", "parent commit")
    return parent


def test_target_inside_another_repository_leaves_it_unchanged(git_env, init_vault, tmp_path):
    parent = _make_parent_repo(tmp_path)
    before = _parent_repo_state(parent)
    target = parent / "vault"
    assert init_vault.main([str(target)]) == 0
    assert _parent_repo_state(parent) == before
    assert len(git(target, "log", "--format=%H").split()) == 1


def test_git_does_not_search_upward_into_a_parent_repository(
    git_env, init_vault, tmp_path, monkeypatch
):
    parent = _make_parent_repo(tmp_path)
    before = _parent_repo_state(parent)
    target = parent / "vault"
    real = init_vault._run_git

    def run(git_, tgt, args):
        out = real(git_, tgt, args)
        if args[0] == "init":  # the new repository vanishes; git must not climb
            shutil.rmtree(target / ".git")
        return out

    monkeypatch.setattr(init_vault, "_run_git", run)
    assert init_vault.main([str(target)]) != 0
    assert _parent_repo_state(parent) == before


def test_file_appearing_after_check_is_not_committed(git_env, init_vault, tmp_path, monkeypatch, capsys):
    target = tmp_path / "v"
    target.mkdir()
    _swap_after_check(monkeypatch, init_vault, lambda p: (p / "late.txt").write_text("x"))
    assert init_vault.main([str(target)]) != 0
    assert "not empty" in capsys.readouterr().err
    assert [p.name for p in target.iterdir()] == ["late.txt"]


@pytest.mark.parametrize("key", ["name", "email"])
@pytest.mark.parametrize("bad", ["a\\nb", "a\rb"])
def test_refuses_identity_with_line_break(git_env, init_vault, tmp_path, key, bad, capsys):
    other = {"name": "email = a@b.c", "email": "name = N"}[key]
    git_env.write_text(f'[user]\n\t{key} = "{bad}"\n\t{other}\n')
    assert init_vault.main([str(tmp_path / "v")]) != 0
    err = capsys.readouterr().err
    assert f"user.{key}" in err and "line break" in err
    assert not (tmp_path / "v").exists()


def test_unreadable_seed_file_is_a_clean_error(git_env, init_vault, tmp_path, monkeypatch, capsys):
    seed = tmp_path / "seed"
    shutil.copytree(SEED, seed)
    victim = seed / "templates" / "task.md"
    victim.chmod(0)
    if os.access(victim, os.R_OK):
        pytest.skip("running with privileges that ignore file modes")
    monkeypatch.setattr(init_vault, "SKILL_DIR", seed)
    target = tmp_path / "v"
    assert init_vault.main([str(target)]) != 0
    err = capsys.readouterr().err
    assert err.startswith("error:") and "Traceback" not in err and "task.md" in err
    assert not target.exists()
    victim.chmod(0o644)


def test_missing_seed_file_is_refused(git_env, init_vault, tmp_path, monkeypatch, capsys):
    seed = tmp_path / "seed"
    shutil.copytree(SEED, seed)
    (seed / "templates" / "lesson.md").unlink()
    monkeypatch.setattr(init_vault, "SKILL_DIR", seed)
    target = tmp_path / "v"
    assert init_vault.main([str(target)]) != 0
    assert "seed file missing" in capsys.readouterr().err
    assert not target.exists()


def test_read_only_parent_is_a_clean_error(git_env, init_vault, tmp_path, capsys):
    parent = tmp_path / "ro"
    parent.mkdir()
    parent.chmod(0o555)
    try:
        if os.access(parent, os.W_OK):
            pytest.skip("running with privileges that ignore directory modes")
        assert init_vault.main([str(parent / "v")]) != 0
        err = capsys.readouterr().err
        assert err.startswith("error:") and "Traceback" not in err
        assert "partial vault" not in err
    finally:
        parent.chmod(0o755)


def test_overlong_name_is_a_clean_error(git_env, init_vault, tmp_path, capsys):
    assert init_vault.main([str(tmp_path / ("x" * 300))]) != 0
    assert capsys.readouterr().err.startswith("error:")


def test_non_utf8_target_path(git_env, init_vault, tmp_path, capsys):
    target = tmp_path / os.fsdecode(b"v\xff\xfe")
    assert init_vault.main([str(target)]) == 0
    assert "Traceback" not in capsys.readouterr().err
    assert (target / ".git").is_dir()


def test_failure_after_writing_started_names_the_partial_vault(
    git_env, init_vault, tmp_path, monkeypatch, capsys
):
    real = init_vault._run_git

    def fail_commit(git, target, args):
        if "commit" in args:
            raise init_vault.InitError("git commit failed: boom")
        return real(git, target, args)

    monkeypatch.setattr(init_vault, "_run_git", fail_commit)
    target = tmp_path / "v"
    assert init_vault.main([str(target)]) != 0
    err = capsys.readouterr().err
    assert "git commit failed" in err
    assert f"partial vault left at {target}; remove it and re-run" in err
    assert target.exists()  # nothing is deleted automatically


def test_failed_git_command_names_the_subcommand(git_env, init_vault, tmp_path, monkeypatch, capsys):
    real_run = subprocess.run

    def failing(cmd, *args, **kwargs):
        if "commit" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "nothing")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(init_vault.subprocess, "run", failing)
    assert init_vault.main([str(tmp_path / "v")]) != 0
    assert "git commit failed: nothing" in capsys.readouterr().err


def test_cli_entry_point(git_env, tmp_path):
    target = tmp_path / "Second Brain"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(target)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert (target / "README.md").is_file()
    again = subprocess.run(
        [sys.executable, str(SCRIPT), str(target)], capture_output=True, text=True
    )
    assert again.returncode != 0
