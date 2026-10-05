"""Tests for claude-workflow/skills/second-brain/scripts/vault_git.py (plan section 4.2).

Every vault here is a temporary repository. The machine's git configuration is
never read or written, the real vault path is replaced by a stand-in, and the
old vault is never named as a filesystem path.
"""

import datetime
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "claude-workflow" / "skills" / "second-brain" / "scripts" / "vault_git.py"
INIT_VAULT = REPO / "second-brain" / "scripts" / "init_vault.py"
TODAY = "2026-10-09"
YESTERDAY = "2026-10-08"
VAULT_NAME = "Second Brain"  # a space in every test vault path


def _load():
    # No __pycache__ beside the script: install.sh copies the skill directory.
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec = importlib.util.spec_from_file_location("vault_git", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def clean_env():
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")} | {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }


# Resolved once, before any test changes PATH.
GIT = shutil.which("git")


def git(repo, *args, check=True):
    return subprocess.run(
        [GIT, "-c", "core.hooksPath=/dev/null", *args], cwd=repo,
        capture_output=True, text=True, check=check, env=clean_env(),
    ).stdout


def make_repo(path, name="Vault User", email="vault@example.com", commit=True):
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main", "--template=")
    for key, value in [("core.autocrlf", "false"), ("core.filemode", "false"),
                       ("core.quotepath", "false")]:
        git(path, "config", key, value)
    if name is not None:
        git(path, "config", "user.name", name)
    if email is not None:
        git(path, "config", "user.email", email)
    if commit:
        (path / "README.md").write_text("# Vault\n")
        git(path, "add", "-A")
        git(path, "commit", "-q", "-m", "Initialize vault")
    return path


def head(repo):
    return git(repo, "rev-parse", "--verify", "-q", "HEAD", check=False).strip()


def subjects(repo):
    return git(repo, "log", "--format=%s").splitlines()


def index_bytes(repo):
    index = repo / ".git" / "index"
    return index.read_bytes() if index.exists() else b""


def staged_names(repo):
    return set(git(repo, "diff", "--cached", "--name-only").splitlines())


def snapshot(root, skip):
    """Every path under root except under skip, with size and mtime."""
    out = []
    for p in sorted(root.rglob("*")):
        if p == skip or skip in p.parents:
            continue
        st = os.lstat(p)
        out.append((p.relative_to(root).as_posix(), st.st_size, st.st_mtime_ns))
    return out


def marker_script(path, marker):
    path.write_text(f'#!/bin/sh\necho ran >> "{marker}"\nexit 0\n')
    path.chmod(0o755)
    return path


# ------------------------------------------------------------------ fixtures


@pytest.fixture
def vg(tmp_path, monkeypatch):
    module = _load()
    # The real vault path is replaced by a stand-in that does not exist.
    monkeypatch.setattr(module, "DEFAULT_VAULT", str(tmp_path / "real-vault-stand-in"))
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    return module


@pytest.fixture
def home(tmp_path_factory, monkeypatch):
    """Isolated global git configuration with an identity that must not be used."""
    home = tmp_path_factory.mktemp("home")
    gitconfig = home / "gitconfig"
    gitconfig.write_text("[user]\n\tname = Global User\n\temail = global@example.com\n")
    for var in [v for v in os.environ if v.startswith("GIT_")]:
        monkeypatch.delenv(var)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return home


@pytest.fixture
def vault(tmp_path, home, monkeypatch):
    path = make_repo(tmp_path / "vaults" / VAULT_NAME)
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(path))
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    monkeypatch.setenv("SECOND_BRAIN_TODAY", TODAY)
    return path


def run(vg, capsys, *argv):
    code = vg.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def cli(*argv, env=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv], capture_output=True, text=True,
        env=env if env is not None else os.environ.copy(),
    )


# ------------------------------------------------------------------ usage


@pytest.mark.parametrize("argv", [
    [], ["bogus"], ["STATUS"], ["status", "x"], ["remote", "-v"], ["stage", "--all"],
    ["staged-diff", "x"], ["head-subject", ""], ["commit-eod"],
    ["commit-eod", TODAY, "x"], ["commit-eod", "-2026-10-09"], ["commit-eod", "--amend"],
    ["--help"], ["-c", "core.pager=x"], ["-C", "/tmp", "status"],
])
def test_usage_errors_exit_2_and_run_nothing(vg, vault, capsys, monkeypatch, argv):
    calls = []
    monkeypatch.setattr(vg.subprocess, "run", lambda *a, **k: calls.append(a))
    code, out, err = run(vg, capsys, *argv)
    assert code == 2
    assert calls == []
    assert out == ""
    assert "usage" in err and err.count("\n") == 1


def test_usage_error_from_the_command_line(vault):
    result = cli("push")
    assert result.returncode == 2
    assert "usage" in result.stderr


def test_refuses_root(vg, vault, capsys, monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    code, out, err = run(vg, capsys, "status")
    assert code == 1 and "root" in err


# ------------------------------------------------------------------ verbs


def test_remote_prints_nothing_without_remotes(vg, vault, capsys):
    assert run(vg, capsys, "remote") == (0, "", "")


def test_remote_lists_configured_remotes(vg, vault, capsys):
    git(vault, "remote", "add", "origin", "/nowhere/a")
    git(vault, "remote", "add", "backup", "/nowhere/b")
    code, out, _ = run(vg, capsys, "remote")
    assert code == 0
    assert sorted(out.splitlines()) == ["backup", "origin"]


def test_status_prints_porcelain(vg, vault, capsys):
    assert run(vg, capsys, "status") == (0, "", "")
    (vault / "README.md").write_text("changed\n")
    (vault / "new note.md").write_text("x\n")
    code, out, _ = run(vg, capsys, "status")
    assert code == 0
    assert out.splitlines() == [" M README.md", '?? "new note.md"'] or \
        out.splitlines() == [" M README.md", "?? new note.md"]


def test_stage_adds_everything(vg, vault, capsys):
    (vault / "README.md").write_text("changed\n")
    (vault / "00-Inbox").mkdir()
    (vault / "00-Inbox" / "a.md").write_text("x\n")
    (vault / "gone.md").write_text("to be deleted\n")
    git(vault, "add", "gone.md")
    git(vault, "commit", "-q", "-m", "add gone")
    (vault / "gone.md").unlink()
    code, out, err = run(vg, capsys, "stage")
    assert (code, err) == (0, "")
    assert staged_names(vault) == {"README.md", "00-Inbox/a.md", "gone.md"}
    assert head(vault)  # nothing committed by stage
    assert subjects(vault)[0] == "add gone"


def test_staged_diff_prints_names_and_diff(vg, vault, capsys):
    (vault / "note.md").write_text("hello world\n")
    git(vault, "add", "-A")
    code, out, _ = run(vg, capsys, "staged-diff")
    assert code == 0
    assert "note.md" in out.split("\n\n", 1)[0]
    assert "+hello world" in out
    assert "diff --git a/note.md b/note.md" in out


def test_staged_diff_is_empty_when_nothing_is_staged(vg, vault, capsys):
    (vault / "unstaged.md").write_text("x\n")
    assert run(vg, capsys, "staged-diff") == (0, "", "")


def test_staged_diff_is_capped(vg, vault, capsys):
    (vault / "big.md").write_text("line of text\n" * 60000)  # ~780 KB
    git(vault, "add", "-A")
    code, out, _ = run(vg, capsys, "staged-diff")
    assert code == 0
    assert len(out.encode()) <= vg.OUTPUT_LIMIT + 300
    assert out.rstrip("\n").splitlines()[-1].startswith("[truncated:")


def test_head_subject(vg, vault, capsys):
    assert run(vg, capsys, "head-subject") == (0, "Initialize vault\n", "")


def test_head_subject_is_empty_without_commits(vg, tmp_path, home, monkeypatch, capsys):
    empty = make_repo(tmp_path / "empty vault", commit=False)
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(empty))
    monkeypatch.delenv("SECOND_BRAIN_TEST_MODE", raising=False)
    assert run(vg, capsys, "head-subject") == (0, "", "")


def test_control_characters_are_escaped(vg, vault, capsys):
    (vault / "a\x1b[31mb.md").write_text("x\n")
    git(vault, "add", "-A")
    git(vault, "commit", "-q", "-m", "evil \x1b[2J subject")
    (vault / "c\x07d.md").write_text("e\x1b[0mf\n")
    git(vault, "add", "-A")
    for verb in ("status", "staged-diff", "head-subject"):
        code, out, err = run(vg, capsys, verb)
        assert code == 0, err
        assert "\x1b" not in out and "\x07" not in out, verb
    assert "\\x1b" in run(vg, capsys, "head-subject")[1]


def test_vault_made_by_init_vault(vg, tmp_path, home, monkeypatch, capsys):
    target = tmp_path / "made" / VAULT_NAME
    gitconfig = Path(os.environ["GIT_CONFIG_GLOBAL"])
    result = subprocess.run([sys.executable, str(INIT_VAULT), str(target)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(target))
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    monkeypatch.setenv("SECOND_BRAIN_TODAY", TODAY)
    gitconfig.write_text("")  # the global identity is gone; the local one is used
    (target / "00-Inbox" / "c.md").write_text("capture\n")
    code, out, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 0, err
    assert subjects(target)[:2] == [f"eod: {TODAY}", "Initialize vault"]


def test_cli_end_to_end(vault):
    (vault / "n.md").write_text("x\n")
    result = cli("commit-eod", TODAY)
    assert result.returncode == 0, result.stderr
    assert subjects(vault)[0] == f"eod: {TODAY}"
    assert cli("head-subject").stdout == f"eod: {TODAY}\n"


# ------------------------------------------------------------- commit-eod


def test_commit_eod_commits_unstaged_and_untracked_changes(vg, vault, capsys):
    (vault / "README.md").write_text("# Vault\nedited\n")
    (vault / "01-Daily").mkdir()
    (vault / "01-Daily" / f"{TODAY}.md").write_text("## Done\n- things\n")
    code, out, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 0, err
    assert subjects(vault) == [f"eod: {TODAY}", "Initialize vault"]
    assert git(vault, "status", "--porcelain") == ""
    assert git(vault, "show", "HEAD:README.md") == "# Vault\nedited\n"
    assert f"eod: {TODAY}" in out
    assert git(vault, "log", "-1", "--format=%an <%ae>|%cn <%ce>").strip() == (
        "Vault User <vault@example.com>|Vault User <vault@example.com>"
    )


def test_second_commit_eod_on_the_same_day_amends(vg, vault, capsys):
    (vault / "a.md").write_text("first\n")
    assert run(vg, capsys, "commit-eod", TODAY)[0] == 0
    first = head(vault)
    (vault / "b.md").write_text("second\n")
    code, out, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 0, err
    assert subjects(vault) == [f"eod: {TODAY}", "Initialize vault"]
    assert head(vault) != first
    assert git(vault, "show", "HEAD:a.md") == "first\n"
    assert git(vault, "show", "HEAD:b.md") == "second\n"
    assert "amend" in out


def test_new_commit_on_top_of_a_previous_days_eod(vg, vault, capsys):
    (vault / "a.md").write_text("x\n")
    git(vault, "add", "-A")
    git(vault, "commit", "-q", "-m", f"eod: {YESTERDAY}")
    (vault / "b.md").write_text("y\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 0, err
    assert subjects(vault) == [f"eod: {TODAY}", f"eod: {YESTERDAY}", "Initialize vault"]


def test_subject_that_only_starts_with_the_message_is_not_amended(vg, vault, capsys):
    (vault / "a.md").write_text("x\n")
    git(vault, "add", "-A")
    git(vault, "commit", "-q", "-m", f"eod: {TODAY} extra")
    (vault / "b.md").write_text("y\n")
    assert run(vg, capsys, "commit-eod", TODAY)[0] == 0
    assert subjects(vault)[:2] == [f"eod: {TODAY}", f"eod: {TODAY} extra"]


def test_commit_eod_in_a_repository_without_commits(vg, tmp_path, home, monkeypatch, capsys):
    empty = make_repo(tmp_path / "empty vault", commit=False)
    (empty / "n.md").write_text("x\n")
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(empty))
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    monkeypatch.setenv("SECOND_BRAIN_TODAY", TODAY)
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 0, err
    assert subjects(empty) == [f"eod: {TODAY}"]


def test_nothing_to_commit_is_an_outcome_and_changes_nothing(vg, vault, capsys):
    before = (head(vault), index_bytes(vault))
    code, out, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 0
    assert out.startswith("nothing to commit") and out.count("\n") == 1
    assert err == ""
    assert (head(vault), index_bytes(vault)) == before


def test_nothing_to_commit_after_todays_commit_changes_nothing(vg, vault, capsys):
    (vault / "a.md").write_text("x\n")
    assert run(vg, capsys, "commit-eod", TODAY)[0] == 0
    before = head(vault)
    code, out, _ = run(vg, capsys, "commit-eod", TODAY)
    assert code == 0 and out.startswith("nothing to commit")
    assert head(vault) == before


@pytest.mark.parametrize("bad", [
    "2026-02-30", "2026-13-01", "2026-00-10", "20261009", "2026-10-9", "26-10-09",
    "２０２６-10-09", "2026-10-09\n", "2026-10-09 ", "", "2026/10/09", "today",
])
def test_bad_date_is_refused_before_anything_changes(vg, vault, capsys, bad):
    (vault / "a.md").write_text("x\n")
    before = (head(vault), index_bytes(vault))
    code, out, err = run(vg, capsys, "commit-eod", bad)
    assert code == 1
    assert "is not a real date" in err and err.count("\n") == 1
    assert (head(vault), index_bytes(vault)) == before


def test_wrong_day_is_refused_in_test_mode(vg, vault, capsys):
    (vault / "a.md").write_text("x\n")
    before = (head(vault), index_bytes(vault))
    code, _, err = run(vg, capsys, "commit-eod", YESTERDAY)
    assert code == 1 and TODAY in err
    assert (head(vault), index_bytes(vault)) == before


def test_test_mode_without_a_pinned_date_refuses_commit(vg, vault, capsys, monkeypatch):
    monkeypatch.delenv("SECOND_BRAIN_TODAY")
    (vault / "a.md").write_text("x\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "SECOND_BRAIN_TODAY" in err
    assert subjects(vault) == ["Initialize vault"]


@pytest.mark.parametrize("verb", ["status", "commit-eod"])
def test_invalid_pinned_date_stops_every_verb(vg, vault, capsys, monkeypatch, verb):
    monkeypatch.setenv("SECOND_BRAIN_TODAY", "2026-02-30")
    args = [verb, "2026-02-30"] if verb == "commit-eod" else [verb]
    code, _, err = run(vg, capsys, *args)
    assert code == 1 and "SECOND_BRAIN_TODAY" in err


def test_outside_test_mode_the_date_must_be_today_in_manila(vg, vault, capsys, monkeypatch):
    monkeypatch.delenv("SECOND_BRAIN_TEST_MODE")
    # The pinned date is ignored outside test mode.
    monkeypatch.setattr(vg, "_manila_today", lambda: datetime.date(2026, 10, 5))
    (vault / "a.md").write_text("x\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "2026-10-05" in err
    code, _, err = run(vg, capsys, "commit-eod", "2026-10-05")
    assert code == 0, err
    assert subjects(vault)[0] == "eod: 2026-10-05"


@pytest.mark.parametrize("utc,manila", [
    ("2026-10-04T15:59:59", "2026-10-04"),   # 23:59:59 in Manila
    ("2026-10-04T16:00:00", "2026-10-05"),   # midnight in Manila, still the 4th in UTC
    ("2026-10-05T15:30:00", "2026-10-05"),
])
def test_today_is_taken_in_manila(vg, monkeypatch, utc, manila):
    instant = datetime.datetime.fromisoformat(utc).replace(tzinfo=datetime.timezone.utc)
    monkeypatch.setattr(vg, "_utc_now", lambda: instant)
    assert vg._manila_today().isoformat() == manila


def test_utc_now_is_the_real_clock(vg):
    before = datetime.datetime.now(datetime.timezone.utc)
    now = vg._utc_now()
    assert now.utcoffset() == datetime.timedelta(0)
    assert abs((now - before).total_seconds()) < 60


@pytest.mark.parametrize("value", ["true", "yes", "01", " 1", "1 ", "0", ""])
def test_test_mode_must_be_exactly_1(vg, stand_in, capsys, monkeypatch, value):
    """Any other value is ordinary mode: the pinned date is ignored and the real
    vault (here its stand-in) is the default, with no test-mode guard."""
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", value)
    monkeypatch.setenv("SECOND_BRAIN_TODAY", TODAY)
    monkeypatch.delenv("SECOND_BRAIN_VAULT", raising=False)
    monkeypatch.setattr(vg, "_manila_today", lambda: datetime.date(2026, 10, 5))
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "is not today (2026-10-05)" in err
    code, out, err = run(vg, capsys, "commit-eod", "2026-10-05")
    assert code == 0, err
    assert subjects(stand_in)[0] == "eod: 2026-10-05"


# -------------------------------------------------------------- remotes


def test_remote_configured_is_refused(vg, vault, capsys):
    git(vault, "remote", "add", "origin", "/nowhere/x")
    (vault / "a.md").write_text("x\n")
    before = (head(vault), index_bytes(vault))
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "remote" in err
    assert (head(vault), index_bytes(vault)) == before


@pytest.mark.parametrize("config", [
    '[remote "x"]\n\turl = /nowhere\n',
    '[remote "x"]\n\tpushurl = /nowhere\n',
    "[remote]\n\tpushDefault = /nowhere\n",
    '[branch "main"]\n\tremote = /nowhere\n',
    '[branch "main"]\n\tpushRemote = /nowhere\n',
])
def test_remote_written_into_config_behind_the_scripts_back(vg, vault, capsys, config):
    with open(vault / ".git" / "config", "a") as fh:
        fh.write(config)
    (vault / "a.md").write_text("x\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "remote" in err
    assert subjects(vault) == ["Initialize vault"]


@pytest.mark.parametrize("folder", ["remotes", "branches"])
def test_legacy_remote_file_is_refused(vg, vault, capsys, folder):
    (vault / ".git" / folder).mkdir()
    (vault / ".git" / folder / "origin").write_text("URL: /nowhere\n")
    (vault / "a.md").write_text("x\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "remote" in err
    assert subjects(vault) == ["Initialize vault"]
    assert "origin" in run(vg, capsys, "remote")[1]


# -------------------------------------------------------------- identity


@pytest.mark.parametrize("missing", ["user.name", "user.email"])
def test_missing_local_identity_is_refused(vg, vault, capsys, monkeypatch, missing):
    git(vault, "config", "--unset", missing)
    for var, value in [("GIT_AUTHOR_NAME", "Env"), ("GIT_AUTHOR_EMAIL", "env@x"),
                       ("GIT_COMMITTER_NAME", "Env"), ("GIT_COMMITTER_EMAIL", "env@x"),
                       ("EMAIL", "env@x")]:
        monkeypatch.setenv(var, value)
    (vault / "a.md").write_text("x\n")
    before = (head(vault), index_bytes(vault))
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and missing in err
    assert (head(vault), index_bytes(vault)) == before


@pytest.mark.parametrize("value", ['"a\\nb"', '""'])
def test_unusable_local_identity_is_refused(vg, vault, capsys, value):
    with open(vault / ".git" / "config", "a") as fh:
        fh.write(f"[user]\n\tname = {value}\n")
    (vault / "a.md").write_text("x\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "user.name" in err
    assert subjects(vault) == ["Initialize vault"]


def test_identity_overrides_are_ignored(vg, vault, capsys, monkeypatch):
    with open(vault / ".git" / "config", "a") as fh:
        fh.write("[author]\n\tname = Evil\n\temail = evil@x\n"
                 "[committer]\n\tname = Evil\n\temail = evil@x\n")
    for var, value in [("GIT_AUTHOR_NAME", "Env"), ("GIT_AUTHOR_EMAIL", "env@x"),
                       ("GIT_COMMITTER_DATE", "2001-01-01T00:00:00")]:
        monkeypatch.setenv(var, value)
    (vault / "a.md").write_text("x\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 0, err
    assert git(vault, "log", "-1", "--format=%an <%ae>|%cn <%ce>").strip() == (
        "Vault User <vault@example.com>|Vault User <vault@example.com>"
    )
    assert not git(vault, "log", "-1", "--format=%cI").startswith("2001")


# ------------------------------------------------------------ secret scan

# Built at run time so the repository holds no literal secret-shaped text.
FILLER = "Q7x" * 12
SECRETS = [
    ("private key", "-----BEGIN " + "RSA PRIVATE KEY-----"),
    ("private key", "-----BEGIN " + "OPENSSH PRIVATE KEY-----"),
    ("private key", "-----BEGIN " + "PGP PRIVATE KEY BLOCK-----"),
    ("password", "password: " + FILLER),
    ("password", "DB_PASSWORD=" + FILLER),
    ("password", '"password": "' + FILLER + '"'),
    ("password", "**Password**: " + FILLER),
    ("token", "access_token = " + FILLER),
    ("secret", "client_secret: " + FILLER),
    ("api key", "API key: " + FILLER),
    ("api key", "api_key=" + FILLER),
    ("api key", "x-api-key: " + FILLER),
    ("GitHub token", "see ghp_" + FILLER),
    ("GitHub token", "github_pat_" + FILLER),
    ("GitLab token", "glpat-" + FILLER),
    ("sk- key", "key sk-" + FILLER),
    ("Slack token", "xoxb-" + FILLER),
    ("AWS access key", "AKIA" + "Q7XZ" * 4),
]


@pytest.mark.parametrize("kind,text", SECRETS)
def test_secret_in_an_untracked_file_is_refused(vg, vault, capsys, kind, text):
    (vault / "notes").mkdir()
    (vault / "notes" / "leak.md").write_text(f"# Note\n\nsome text\n{text}\n")
    (vault / "clean.md").write_text("fine\n")
    before = head(vault)
    code, out, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1
    assert "notes/leak.md" in err and kind in err
    assert "clean.md" not in err
    assert err.count("\n") == 1
    secret_part = text.split()[-1].strip('"')
    assert secret_part not in out + err
    assert FILLER not in out + err
    assert head(vault) == before
    # Decision: the refusal leaves the changes staged.
    assert "notes/leak.md" in staged_names(vault)


def test_secret_in_a_modified_tracked_file_is_refused(vg, vault, capsys):
    (vault / "README.md").write_text("# Vault\ntoken: " + FILLER + "\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "README.md" in err and "token" in err
    assert subjects(vault) == ["Initialize vault"]


def test_added_line_that_looks_like_a_diff_header_is_scanned(vg, vault, capsys):
    (vault / "a.md").write_text("++ password = " + FILLER + "\n++ b/other\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "a.md:1 (password)" in err


def test_secret_in_a_binary_file_is_refused(vg, vault, capsys):
    (vault / "blob.bin").write_bytes(b"\x00\x01\x02ghp_" + FILLER.encode() + b"\x00\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "blob.bin" in err


def test_secret_on_amend_is_refused_and_keeps_the_existing_commit(vg, vault, capsys):
    (vault / "a.md").write_text("x\n")
    assert run(vg, capsys, "commit-eod", TODAY)[0] == 0
    before = head(vault)
    (vault / "b.md").write_text("secret = " + FILLER + "\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "b.md" in err
    assert head(vault) == before


def test_file_name_in_a_refusal_is_escaped(vg, vault, capsys):
    (vault / "x\x1b[2Jy.md").write_text("token: " + FILLER + "\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1
    assert "\x1b" not in err and "\\x1b" in err


def test_each_matching_line_is_reported_with_its_number(vg, vault, capsys):
    (vault / "a.md").write_text("intro\n" + ("token: " + FILLER + "\n") * 3)
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1
    assert "a.md:2 (token), a.md:3 (token), a.md:4 (token)" in err


def test_removing_a_secret_is_allowed(vg, vault, capsys):
    (vault / "a.md").write_text("keep\npassword: " + FILLER + "\n")
    git(vault, "add", "-A")
    git(vault, "commit", "-q", "-m", "old")
    (vault / "a.md").write_text("keep\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 0, err


@pytest.mark.parametrize("text", [
    "password:", "password: ", 'password: ""', "password = ''", "password: ***",
    "the ghp_ prefix marks a token", "a risk-free task-based plan with sk-short",
    "secret sauce", "tokens are counted", "token_count: 5", "AKIA is a prefix",
    "Passwords should be rotated", "glpat-short",
])
def test_harmless_text_is_committed_basic(vg, vault, capsys, text):
    (vault / "a.md").write_text(text + "\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 0, err


# ------------------------------------------------------------ vault checks


def _refused(vg, capsys, monkeypatch, path, verb="status"):
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(path))
    code, out, err = run(vg, capsys, verb)
    assert code == 1, err
    assert out == "" and err.count("\n") == 1
    return err


def test_missing_vault(vg, home, tmp_path, capsys, monkeypatch):
    assert "does not exist" in _refused(vg, capsys, monkeypatch, tmp_path / "nope")


def test_vault_is_a_file(vg, home, tmp_path, capsys, monkeypatch):
    (tmp_path / "file").write_text("x")
    assert "not a directory" in _refused(vg, capsys, monkeypatch, tmp_path / "file")


def test_vault_is_a_symlink(vg, vault, tmp_path, capsys, monkeypatch):
    link = tmp_path / "link"
    link.symlink_to(vault)
    assert "the vault is a symlink" in _refused(vg, capsys, monkeypatch, link, "stage")


def test_vault_path_through_a_symlinked_parent(vg, vault, tmp_path, capsys, monkeypatch):
    link = tmp_path / "linked-parent"
    link.symlink_to(vault.parent)
    assert "symlink" in _refused(vg, capsys, monkeypatch, link / VAULT_NAME)


@pytest.mark.parametrize("raw", ["", "relative/vault", "./x"])
def test_vault_must_be_absolute(vg, home, capsys, monkeypatch, raw):
    assert "absolute" in _refused(vg, capsys, monkeypatch, raw)


def test_vault_path_with_dotdot(vg, vault, capsys, monkeypatch):
    path = f"{vault}/../{VAULT_NAME}"
    assert ".." in _refused(vg, capsys, monkeypatch, path)


def test_dot_segments_and_trailing_slash_are_accepted(vg, vault, capsys, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_VAULT", f"{vault.parent}/./{VAULT_NAME}/")
    assert run(vg, capsys, "status")[0] == 0


def test_git_file_instead_of_directory(vg, home, tmp_path, capsys, monkeypatch):
    other = make_repo(tmp_path / "other")
    fake = tmp_path / "fake"
    fake.mkdir()
    (fake / ".git").write_text(f"gitdir: {other / '.git'}\n")
    (fake / "a.md").write_text("x\n")
    before = (head(other), index_bytes(other))
    err = _refused(vg, capsys, monkeypatch, fake, "stage")
    assert ".git is not a directory" in err
    assert (head(other), index_bytes(other)) == before


def test_git_symlink_instead_of_directory(vg, home, tmp_path, capsys, monkeypatch):
    other = make_repo(tmp_path / "other")
    fake = tmp_path / "fake"
    fake.mkdir()
    (fake / ".git").symlink_to(other / ".git")
    before = index_bytes(other)
    assert ".git is a symlink" in _refused(vg, capsys, monkeypatch, fake, "stage")
    assert index_bytes(other) == before


def test_directory_without_git(vg, home, tmp_path, capsys, monkeypatch):
    (tmp_path / "plain").mkdir()
    assert ".git" in _refused(vg, capsys, monkeypatch, tmp_path / "plain")


def test_subdirectory_of_a_repository(vg, home, tmp_path, capsys, monkeypatch):
    repo = make_repo(tmp_path / "repo")
    (repo / "sub").mkdir()
    (repo / "sub" / "a.md").write_text("x\n")
    before = index_bytes(repo)
    _refused(vg, capsys, monkeypatch, repo / "sub", "stage")
    assert index_bytes(repo) == before


def test_core_worktree_pointing_elsewhere_is_refused(vg, vault, tmp_path, capsys, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "stolen.md").write_text("x\n")
    git(vault, "config", "core.worktree", str(elsewhere))
    assert "top level" in _refused(vg, capsys, monkeypatch, vault, "stage")
    assert "stolen.md" not in git(vault, "ls-files", check=False)


def test_bare_repository_is_refused(vg, vault, capsys, monkeypatch):
    git(vault, "config", "core.bare", "true")
    _refused(vg, capsys, monkeypatch, vault, "stage")


def test_commondir_redirect_is_refused(vg, vault, tmp_path, capsys, monkeypatch):
    other = make_repo(tmp_path / "other")
    (vault / ".git" / "commondir").write_text(str(other / ".git") + "\n")
    (vault / "a.md").write_text("x\n")
    before = (head(other), (other / ".git" / "config").read_bytes())
    assert "commondir" in _refused(vg, capsys, monkeypatch, vault, "stage")
    assert (head(other), (other / ".git" / "config").read_bytes()) == before


def test_alternates_are_refused(vg, vault, tmp_path, capsys, monkeypatch):
    other = make_repo(tmp_path / "other")
    (vault / ".git" / "objects" / "info").mkdir(exist_ok=True)
    (vault / ".git" / "objects" / "info" / "alternates").write_text(
        str(other / ".git" / "objects") + "\n")
    assert "alternates" in _refused(vg, capsys, monkeypatch, vault)


@pytest.mark.parametrize("name", ["config", "objects", "refs", "HEAD"])
def test_symlinked_repository_internals_are_refused(vg, vault, tmp_path, capsys,
                                                    monkeypatch, name):
    other = make_repo(tmp_path / "other")
    target = vault / ".git" / name
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    target.symlink_to(other / ".git" / name)
    assert "symlink" in _refused(vg, capsys, monkeypatch, vault)


def test_old_vault_and_drive_c_are_refused_without_filesystem_access(
    vg, home, capsys, monkeypatch
):
    seen = []
    real_lstat = os.lstat

    def lstat(path, *a, **k):
        if os.fsdecode(path).casefold().startswith("/mnt/c"):
            seen.append(path)
        return real_lstat(path, *a, **k)

    monkeypatch.setattr(os, "lstat", lstat)
    for raw in ("/mnt/c/Users/User/Documents/Obsidian Vault", "/MNT/C/anything",
                "/mnt/c", "//mnt/c/x"):
        _refused(vg, capsys, monkeypatch, raw)
    assert seen == []


# ---------------------------------------------------------- test-mode guard


def test_default_vault_constant_is_the_real_path():
    assert _load().DEFAULT_VAULT == "/mnt/d/Second Brain"


@pytest.fixture
def stand_in(vg, home, tmp_path):
    """A stand-in for the real vault, holding a real repository."""
    path = make_repo(Path(vg.DEFAULT_VAULT))
    (path / "pending.md").write_text("x\n")
    return path


def test_test_mode_with_vault_unset_is_refused(vg, stand_in, capsys, monkeypatch):
    monkeypatch.delenv("SECOND_BRAIN_VAULT", raising=False)
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    monkeypatch.setenv("SECOND_BRAIN_TODAY", TODAY)
    before = (head(stand_in), index_bytes(stand_in))
    for argv in (["status"], ["stage"], ["commit-eod", TODAY]):
        code, _, err = run(vg, capsys, *argv)
        assert code == 1 and "SECOND_BRAIN_VAULT" in err
    assert (head(stand_in), index_bytes(stand_in)) == before


@pytest.mark.parametrize("build", [
    lambda p: str(p),
    lambda p: str(p) + "/",
    lambda p: str(p.parent) + "/./" + p.name,
    lambda p: str(p.parent) + "//" + p.name,
    lambda p: str(p).swapcase(),
])
def test_test_mode_pointing_at_the_real_vault_is_refused(vg, stand_in, capsys, monkeypatch,
                                                         build):
    monkeypatch.setenv("SECOND_BRAIN_VAULT", build(stand_in))
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    monkeypatch.setenv("SECOND_BRAIN_TODAY", TODAY)
    before = (head(stand_in), index_bytes(stand_in))
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "real vault" in err
    assert (head(stand_in), index_bytes(stand_in)) == before


def test_test_mode_pointing_at_the_real_vault_through_a_symlink(
    vg, stand_in, tmp_path, capsys, monkeypatch
):
    link = tmp_path / "alias"
    link.symlink_to(stand_in)
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(link))
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    monkeypatch.setenv("SECOND_BRAIN_TODAY", TODAY)
    before = index_bytes(stand_in)
    code, _, err = run(vg, capsys, "stage")
    assert code == 1 and "real vault" in err
    assert index_bytes(stand_in) == before


def test_outside_test_mode_the_default_vault_is_used(vg, stand_in, capsys, monkeypatch):
    monkeypatch.delenv("SECOND_BRAIN_VAULT", raising=False)
    monkeypatch.delenv("SECOND_BRAIN_TEST_MODE", raising=False)
    code, out, _ = run(vg, capsys, "status")
    assert code == 0 and "pending.md" in out


# ------------------------------------------------------------ hostile cases


def _all_verbs(vg, capsys):
    """Run every verb; return the commit-eod result."""
    results = {}
    for argv in (["remote"], ["status"], ["stage"], ["staged-diff"], ["head-subject"],
                 ["commit-eod", TODAY]):
        results[argv[0]] = run(vg, capsys, *argv)
    return results


@pytest.fixture
def hostile(vault, tmp_path):
    """A marker that must never appear, and a snapshot of everything outside the vault."""
    marker = tmp_path / "MARKER"
    (vault / "today.md").write_text("work\n")

    def check(results=None):
        assert not marker.exists(), marker.read_text()
        if results is not None:
            assert results["commit-eod"][0] == 0, results["commit-eod"][2]
            assert subjects(vault)[0] == f"eod: {TODAY}"

    check.marker = marker
    check.outside = lambda: snapshot(tmp_path, vault)
    return check


def _local_config(vault, text):
    with open(vault / ".git" / "config", "a") as fh:
        fh.write(text)


@pytest.mark.parametrize("setting", [
    "core.hooksPath={hooks}",
    "core.fsmonitor={script}",
    "core.pager={script}",
    "core.editor={script}",
    "core.sshCommand={script}",
    "core.askPass={script}",
    "credential.helper=!{script}",
    "diff.external={script}",
    "alias.status=!{script}",
    "alias.add=!{script}",
    "alias.commit=!{script}",
    "pager.status={script}",
    "pager.diff={script}",
    "gpg.program={script}",
    "commit.gpgSign=true\n\tgpg.program={script}",
    "log.showSignature=true\n\tgpg.program={script}",
    "sequence.editor={script}",
    "gc.auto=1",
    "core.gitProxy={script}",
])
def test_hostile_local_config_runs_nothing(vg, vault, hostile, tmp_path, capsys, setting):
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    for name in ("pre-commit", "post-commit", "commit-msg", "prepare-commit-msg",
                 "post-index-change", "reference-transaction", "post-rewrite",
                 "pre-auto-gc"):
        marker_script(hooks / name, hostile.marker)
    script = marker_script(tmp_path / "prog", hostile.marker)
    lines = setting.format(hooks=hooks, script=script).split("\n\t")
    text = ""
    for line in lines:
        key, value = line.split("=", 1)
        section, _, name = key.rpartition(".")
        text += f'[{section}]\n\t{name} = "{value}"\n'
    _local_config(vault, text)
    for i in range(3):  # loose objects for gc.auto=1
        (vault / f"extra{i}.md").write_text(f"{i}\n")
    before = hostile.outside()
    results = _all_verbs(vg, capsys)
    hostile(results)
    assert hostile.outside() == before


def test_signed_head_with_show_signature_runs_nothing(vg, vault, hostile, tmp_path, capsys):
    script = marker_script(tmp_path / "prog", hostile.marker)
    _local_config(vault, f'[log]\n\tshowSignature = true\n[gpg]\n\tprogram = "{script}"\n')
    results = _all_verbs(vg, capsys)
    hostile(results)
    assert results["head-subject"][0] == 0


def test_hooks_in_the_repository_do_not_run(vg, vault, hostile, capsys):
    hooks = vault / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    for name in ("pre-commit", "post-commit", "commit-msg", "prepare-commit-msg",
                 "post-index-change", "reference-transaction", "post-rewrite"):
        marker_script(hooks / name, hostile.marker)
    before = hostile.outside()
    hostile(_all_verbs(vg, capsys))
    (vault / "more.md").write_text("y\n")  # the amend path too
    assert run(vg, capsys, "commit-eod", TODAY)[0] == 0
    hostile()
    assert hostile.outside() == before


@pytest.mark.parametrize("config,attributes", [
    ('[filter "x"]\n\tclean = "{script}"\n\tsmudge = "{script}"\n', "* filter=x\n"),
    ('[filter "x"]\n\tprocess = "{script}"\n', "* filter=x\n"),
    ('[diff "x"]\n\ttextconv = "{script}"\n', "* diff=x\n"),
    ('[diff "x"]\n\tcommand = "{script}"\n', "* diff=x\n"),
    ('[merge "x"]\n\tdriver = "{script}"\n', "* merge=x\n"),
    ('[hook "x"]\n\tcommand = "{script}"\n\tevent = pre-commit\n', ""),
    ('[include]\n\tpath = "{incl}"\n', ""),
    ('[includeIf "gitdir:/"]\n\tpath = "{incl}"\n', ""),
])
@pytest.mark.parametrize("info_attributes", [False, True])
def test_program_naming_config_is_refused(vg, vault, hostile, tmp_path, capsys,
                                          config, attributes, info_attributes):
    script = marker_script(tmp_path / "prog", hostile.marker)
    incl = tmp_path / "included"
    incl.write_text(f'[core]\n\tfsmonitor = "{script}"\n')
    _local_config(vault, config.format(script=script, incl=incl))
    if info_attributes:
        (vault / ".git" / "info").mkdir(exist_ok=True)
        (vault / ".git" / "info" / "attributes").write_text(attributes)
    else:
        (vault / ".gitattributes").write_text(attributes)
    before = (head(vault), index_bytes(vault), hostile.outside())
    for argv in (["status"], ["stage"], ["staged-diff"], ["commit-eod", TODAY]):
        code, _, err = run(vg, capsys, *argv)
        assert code == 1 and "configuration" in err, argv
    hostile()
    assert (head(vault), index_bytes(vault), hostile.outside()) == before


@pytest.mark.parametrize("config", [
    '[diff "x"]\n\ttextconv = "{script}"\n',
    '[diff "x"]\n\tcommand = "{script}"\n',
])
def test_diff_drivers_do_not_run_even_past_the_config_check(
    vg, vault, hostile, tmp_path, capsys, monkeypatch, config
):
    """The --no-textconv and --no-ext-diff flags hold on their own."""
    monkeypatch.setattr(vg, "_check_config", lambda repo: None)
    script = marker_script(tmp_path / "prog", hostile.marker)
    _local_config(vault, config.format(script=script))
    (vault / ".gitattributes").write_text("* diff=x\n")
    (vault / "README.md").write_text("changed\n")
    git(vault, "add", "-A")
    assert run(vg, capsys, "staged-diff")[0] == 0
    assert run(vg, capsys, "commit-eod", TODAY)[0] == 0
    hostile()


def test_hostile_git_environment(vg, vault, hostile, tmp_path, capsys, monkeypatch):
    other = make_repo(tmp_path / "other")
    (other / "other-file.md").write_text("x\n")
    script = marker_script(tmp_path / "prog", hostile.marker)
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    for name in ("pre-commit", "post-commit", "post-index-change"):
        marker_script(hooks / name, hostile.marker)
    other_state = (head(other), index_bytes(other), (other / ".git" / "config").read_bytes())
    env = {
        "GIT_DIR": str(other / ".git"),
        "GIT_WORK_TREE": str(other),
        "GIT_INDEX_FILE": str(tmp_path / "evil-index"),
        "GIT_OBJECT_DIRECTORY": str(tmp_path / "evil-objects"),
        "GIT_COMMON_DIR": str(other / ".git"),
        "GIT_CONFIG_COUNT": "3",
        "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": str(hooks),
        "GIT_CONFIG_KEY_1": "core.worktree", "GIT_CONFIG_VALUE_1": str(other),
        "GIT_CONFIG_KEY_2": "core.fsmonitor", "GIT_CONFIG_VALUE_2": str(script),
        "GIT_CONFIG_PARAMETERS": f"'core.fsmonitor'='{script}'",
        "GIT_CONFIG_SYSTEM": str(tmp_path / "sys"),
        "GIT_CONFIG_NOSYSTEM": "0",
        "GIT_TRACE": str(tmp_path / "trace"),
        "GIT_TRACE_SETUP": str(tmp_path / "trace-setup"),
        "GIT_TRACE_PACKET": str(tmp_path / "trace-packet"),
        "GIT_TRACE2": str(tmp_path / "trace2"),
        "GIT_TRACE2_EVENT": str(tmp_path / "trace2-event"),
        "GIT_EXTERNAL_DIFF": str(script),
        "GIT_PAGER": str(script), "PAGER": str(script),
        "GIT_EDITOR": str(script), "EDITOR": str(script), "VISUAL": str(script),
        "GIT_SSH_COMMAND": str(script), "GIT_ASKPASS": str(script),
        "SSH_ASKPASS": str(script),
        "GIT_ALLOW_PROTOCOL": "file:ext",
        "GIT_CEILING_DIRECTORIES": "",
        "GIT_AUTHOR_NAME": "Env", "GIT_COMMITTER_EMAIL": "env@x",
    }
    (tmp_path / "sys").write_text(f'[core]\n\thooksPath = "{hooks}"\n')
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    results = _all_verbs(vg, capsys)
    hostile(results)
    assert (head(other), index_bytes(other),
            (other / ".git" / "config").read_bytes()) == other_state
    assert "other-file.md" not in results["status"][1]
    for name in ("trace", "trace-setup", "trace-packet", "trace2", "trace2-event",
                 "evil-index", "evil-objects"):
        assert not (tmp_path / name).exists(), name
    assert git(vault, "log", "-1", "--format=%an").strip() == "Vault User"


def test_hostile_global_config(vg, vault, hostile, home, tmp_path, capsys):
    script = marker_script(tmp_path / "prog", hostile.marker)
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    for name in ("pre-commit", "post-commit", "post-index-change"):
        marker_script(hooks / name, hostile.marker)
    text = (f'[core]\n\thooksPath = "{hooks}"\n\tfsmonitor = "{script}"\n'
            f'[filter "x"]\n\tclean = "{script}"\n'
            '[remote "origin"]\n\turl = /nowhere\n')
    for path in (Path(os.environ["GIT_CONFIG_GLOBAL"]), home / ".gitconfig",
                 home / "xdg" / "git" / "config"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    (home / "xdg" / "git" / "attributes").write_text("* filter=x\n")
    hostile(_all_verbs(vg, capsys))


def test_hostile_path_does_not_choose_git(vg, vault, hostile, tmp_path, capsys, monkeypatch):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    marker_script(fake_bin / "git", hostile.marker)
    monkeypatch.setenv("PATH", f"{fake_bin}:{os.environ['PATH']}")
    hostile(_all_verbs(vg, capsys))


def test_vault_swapped_for_a_symlink_between_calls(vg, vault, tmp_path, capsys, monkeypatch):
    elsewhere = make_repo(tmp_path / "elsewhere")
    (elsewhere / "victim.md").write_text("x\n")
    state = (head(elsewhere), index_bytes(elsewhere))
    real_run = vg.subprocess.run
    calls = []

    def swapping(cmd, *args, **kwargs):
        result = real_run(cmd, *args, **kwargs)
        if "--no-pager" in cmd:  # the script's calls, not this test's
            calls.append(cmd)
        if len(calls) == 1 and not (tmp_path / "moved").exists():
            vault.rename(tmp_path / "moved")
            vault.symlink_to(elsewhere)
        return result

    monkeypatch.setattr(vg.subprocess, "run", swapping)
    (vault / "a.md").write_text("x\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "changed" in err
    assert (head(elsewhere), index_bytes(elsewhere)) == state
    assert len(calls) == 1


def test_git_dir_swapped_between_calls(vg, vault, tmp_path, capsys, monkeypatch):
    elsewhere = make_repo(tmp_path / "elsewhere")
    state = (head(elsewhere), index_bytes(elsewhere))
    real_run = vg.subprocess.run
    calls = []

    def swapping(cmd, *args, **kwargs):
        result = real_run(cmd, *args, **kwargs)
        if "--no-pager" in cmd:
            calls.append(cmd)
        if len(calls) == 1 and not (tmp_path / "moved-git").exists():
            (vault / ".git").rename(tmp_path / "moved-git")
            (vault / ".git").symlink_to(elsewhere / ".git")
        return result

    monkeypatch.setattr(vg.subprocess, "run", swapping)
    (vault / "a.md").write_text("x\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "changed" in err
    assert (head(elsewhere), index_bytes(elsewhere)) == state


PINS = [
    "core.hooksPath=/dev/null", "core.fsmonitor=false", "core.pager=cat",
    "core.sshCommand=false", "credential.helper=", "core.editor=false",
    "core.askPass=false", "diff.external=", "gpg.program=false", "commit.gpgSign=false",
    "protocol.allow=never", "log.showSignature=false", "core.attributesFile=/dev/null",
    "core.excludesFile=/dev/null", "gc.auto=0", "maintenance.auto=false",
]


def test_every_git_call_is_isolated(vg, vault, capsys, monkeypatch):
    calls = []
    real_run = vg.subprocess.run

    def spy(cmd, *args, **kwargs):
        calls.append((cmd, kwargs))
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(vg.subprocess, "run", spy)
    monkeypatch.setenv("GIT_DIR", "/nowhere")
    (vault / "a.md").write_text("x\n")
    for argv in (["remote"], ["status"], ["stage"], ["staged-diff"], ["head-subject"],
                 ["commit-eod", TODAY]):
        assert run(vg, capsys, *argv)[0] == 0, argv
    assert len(calls) > 20
    for cmd, kwargs in calls:
        assert isinstance(cmd, list) and not kwargs.get("shell")
        assert cmd[0] == "/usr/bin/git"
        assert "--no-pager" in cmd
        pairs = [cmd[i + 1] for i, part in enumerate(cmd) if part == "-c"]
        for pin in PINS:
            assert pin in pairs, (pin, cmd)
        env = kwargs["env"]
        assert env["GIT_CONFIG_NOSYSTEM"] == "1"
        assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"
        assert env["GIT_ALLOW_PROTOCOL"] == ""
        assert env["GIT_CEILING_DIRECTORIES"] == str(vault.parent)
        assert set(env) <= {"PATH", "HOME", "LC_ALL", "GIT_CONFIG_NOSYSTEM",
                            "GIT_CONFIG_GLOBAL", "GIT_ALLOW_PROTOCOL",
                            "GIT_CEILING_DIRECTORIES", "GIT_TERMINAL_PROMPT"}
        assert kwargs["cwd"] == str(vault)
        if "rev-parse" not in cmd or "--show-toplevel" not in cmd:
            assert f"--git-dir={vault}/.git" in cmd
            assert f"--work-tree={vault}" in cmd
    diffs = [cmd for cmd, _ in calls if "diff" in cmd]
    assert diffs
    for cmd in diffs:
        assert "--no-ext-diff" in cmd and "--no-textconv" in cmd
    commits = [cmd for cmd, _ in calls if "commit" in cmd]
    assert commits and all("--no-verify" in c and "--no-gpg-sign" in c for c in commits)


# ============================================ review round 2: secret scan rules

# Fake values only. Pieces are joined at run time so this file holds no
# literal secret-shaped text.
FAKE_DJANGO = "django-insecure-" + "4f8a9c2e7b1d3f6a0e5c"
FAKE_AWS_SECRET = "wJalrXUtnFEMI" + "/K7MDENG/bPxRfiCYFAKEKEY"
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9" + ".eyJzdWIiOiJmYWtlIn0.c2lnbmF0dXJlZmFrZQ"

# Each of these, alone in an added line, must not block the commit.
NOT_SECRETS = [
    "Rotate the API key: done",
    "- [x] Rotate the API key: done",
    "password: <your password>",
    "token: ${TOKEN}",
    "password: {{ vault_password }}",
    "password = os.environ['DB_PASSWORD']",
    "token = request.headers.get('Authorization')",
    "secret = get_secret('db')",
    "Secret: the cache is Redis",
    "**Token**: the refresh flow is broken",
    "password: changeme",
    "password: REDACTED",
    "password: None",
    "Password: stored in 1Password",
    "csrf_token = {% csrf_token %}",
    "max_token: 4096",
    "## Secret: management",
    "DB_PASSWORD=${DB_PASSWORD}",
    "skip: sk-learn-preprocessing-pipeline-notes",
    # decisions where the plan's rules leave a case open (see the report)
    "secret_name: prod-db-credentials",
    "DB_PASS=hunter2",
    "password: $DB_PASSWORD",
    "password: xxxxxxxxxx",
    "token: ********",
    "api_key: settings.API_KEY",
    "token_url: https://auth.example.com/oauth/token",
    "secret_path: /run/secrets/db_password",
    "token_type: refresh_token",
    "passenger: Abcdef123456",
    "bypass: Abcdef123456",
    "| password | stored in the team vault |",
    "| Key | Value |",
    "postgres://app:${DB_PASSWORD}@db/app",
    "https://user:<password>@host/path",
    "Authorization: Bearer <token>",
    "Authorization: Bearer $TOKEN",
    "task-2026-10-09-retrospective-notes-and-actions",
    "AKIA" + "Q7XZ" * 4 + "Q",
    "ASIAPACIFICREGIONSALES",
    "see ghp_" + "abcdefghijklmnopqrstuvwxyz",
]


@pytest.mark.parametrize("text", NOT_SECRETS)
def test_harmless_line_is_committed(vg, vault, capsys, text):
    (vault / "note.md").write_text("# Note\n\n" + text + "\n")
    code, out, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 0, err
    assert subjects(vault)[0] == f"eod: {TODAY}"


# (kind, added lines) that must be caught; the reported line is the last one.
SECRET_LINES = [
    ("secret", ["SECRET_KEY = '" + FAKE_DJANGO + "'"]),
    ("secret", ["AWS_SECRET_ACCESS_KEY=" + FAKE_AWS_SECRET]),
    ("secret", ["aws_secret_access_key = " + FAKE_AWS_SECRET]),
    ("secret", ["secretKey: Fk3" + "Qz9Lm2Vx8"]),
    ("private key", ["private_key: 3f9a8b7c" + "6d5e4f3a"]),
    ("password", ["DB_PASS=Fake-Pass-" + "2024"]),
    ("password", ["pwd: Fak3" + "Pwd99x"]),
    ("password", ["passwd: Fak3" + "Passwd9"]),
    ("password", ["passphrase: Correct-" + "Horse-9"]),
    ("password", ["password = 'Fake-" + "Pa55word'"]),
    ("password", ['"password": "Fake-' + 'Pa55word",']),
    ("password", ["DB_PASSWORD=hunter" + "2hunter2"]),
    ("password", ["password: Abc12345" + "XYZ  # prod"]),
    ("token", ["access_token: Q7x" + "Q7xQ7xQ7x"]),
    ("token", ["**Token**: Q7x" + "Q7xQ7xQ7x"]),
    ("api key", ["API key: Q7x" + "Q7xQ7xQ7x"]),
    ("api key", ["x-api-key: Q7x" + "Q7xQ7xQ7x"]),
    ("URL credentials", ["postgres://app:Fake-" + "Pw-123@db/app"]),
    ("URL credentials", ["https://user:Fake" + "Pw42@host"]),
    ("URL credentials", ["https://user:pw@host"]),
    ("authorization header", ["Authorization: Bearer " + FAKE_JWT]),
    ("authorization header", ['-H "Authorization: Basic ' + "ZmFrZTpmYWtlcGFzcw==" + '"']),
    ("AWS access key", ["ASIA" + "Q7XZ" * 4]),
    ("AWS access key", ["AKIA" + "Q7XZ" * 4]),
    ("password", ["| user | password |", "| --- | --- |", "| admin | x |",
                  "| password | Fake-" + "Pa55word |"]),
    ("token", ["| **API token** | `Q7x" + "Q7xQ7xQ7x` |"]),
    ("password", ["password:", "  Fake-" + "Pa55word"]),
    ("token", ["- token:", "  Q7x" + "Q7xQ7xQ7x"]),
]


@pytest.mark.parametrize("kind,lines", SECRET_LINES,
                         ids=[f"{k}:{lines[-1][:24]}" for k, lines in SECRET_LINES])
def test_secret_line_is_caught(vg, vault, capsys, kind, lines):
    (vault / "note.md").write_text("# Note\n\n" + "\n".join(lines) + "\n")
    code, out, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1, out
    assert f"note.md:{2 + len(lines)} ({kind})" in err
    for line in lines:
        for word in line.split():
            if len(word) >= 8 and any(c.isdigit() for c in word):
                assert word.strip("'\"`|,") not in out + err
    assert subjects(vault) == ["Initialize vault"]


@pytest.mark.parametrize("prefix", ["ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_"])
def test_each_github_prefix_is_caught(vg, vault, capsys, prefix):
    (vault / "note.md").write_text("see " + prefix + FILLER + "\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "note.md:1 (GitHub token)" in err


@pytest.mark.parametrize("prefix,kind", [("glpat-", "GitLab token"), ("sk-", "sk- key"),
                                         ("xoxb-", "Slack token")])
def test_other_token_prefixes_are_caught(vg, vault, capsys, prefix, kind):
    (vault / "note.md").write_text("(" + prefix + FILLER + ")\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and f"note.md:1 ({kind})" in err


def test_secret_in_an_added_file_name_is_caught_and_not_printed(vg, vault, capsys):
    name = "ghp_" + FILLER + ".md"
    (vault / "00-Inbox").mkdir()
    (vault / "00-Inbox" / name).write_text("password: Fake-" + "Pa55word\n")
    code, out, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1
    assert "file name" in err and "GitHub token" in err
    assert FILLER not in out + err and name not in out + err
    assert "(password)" in err  # the content match, under a redacted label


def test_a_tab_after_a_file_name_with_spaces_is_not_part_of_the_name(vg, vault, capsys):
    (vault / "01-Daily").mkdir()
    (vault / "01-Daily" / "my daily note.md").write_text("token: " + FILLER + "\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1
    assert "01-Daily/my daily note.md:1 (token)" in err


def test_escape_hatch_skips_only_the_marked_line(vg, vault, capsys):
    mark = "<!-- sbw: not-a-secret -->"
    (vault / "note.md").write_text(
        f"token: {FILLER} {mark}\n"
        f"password: Fake-Pa55word {mark}\n"
        f"secret: {FILLER}\n"
    )
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1
    assert "note.md:3 (secret)" in err
    assert "note.md:1" not in err and "note.md:2" not in err
    (vault / "note.md").write_text(f"token: {FILLER} {mark}\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 0, err


def test_escape_hatch_must_be_exact(vg, vault, capsys):
    (vault / "note.md").write_text(f"token: {FILLER} <!-- not-a-secret -->\n")
    assert run(vg, capsys, "commit-eod", TODAY)[0] == 1


def test_refusal_lists_ten_matches_then_how_many_more(vg, vault, capsys):
    (vault / "note.md").write_text("".join(f"token: {FILLER}{i:02d}\n" for i in range(13)))
    code, out, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1
    assert err.startswith("refused: ") and err.count("\n") == 1
    entries = [f"note.md:{n} (token)" for n in range(1, 14)]
    assert all(e in err for e in entries[:10])
    assert entries[10] not in err and "and 3 more" in err
    assert "Remove the value" in err and "<!-- sbw: not-a-secret -->" in err
    assert "/eod" in err
    assert FILLER not in out + err and "token: " not in out + err
    assert head(vault) and subjects(vault) == ["Initialize vault"]
    assert "note.md" in staged_names(vault)  # left staged


def test_secret_text_never_appears_in_any_output(vg, vault, capsys):
    secrets = ["Fake-" + "Pa55word", FILLER, "ghp_" + FILLER, FAKE_JWT]
    (vault / "note.md").write_text(
        f"password: {secrets[0]}\nkey: {secrets[2]}\nAuthorization: Bearer {secrets[3]}\n"
        f"token = '{secrets[1]}'\n")
    code, out, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1
    for secret in secrets:
        assert secret not in out and secret not in err
    assert "note.md:1 (password)" in err and "note.md:4 (token)" in err


# ======================================== review round 2: repository state


@pytest.mark.parametrize("where", ["COMMIT_EDITMSG", "logs", "refs/heads/sub"])
def test_symlink_anywhere_under_git_is_refused(vg, vault, tmp_path, capsys, where):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "victim.txt").write_text("precious\n")
    link = vault / ".git" / where
    if where == "COMMIT_EDITMSG":
        link.unlink(missing_ok=True)
        link.symlink_to(outside / "victim.txt")
    else:
        if link.exists():
            shutil.rmtree(link)
        link.symlink_to(outside, target_is_directory=True)
    (vault / "a.md").write_text("x\n")
    before = snapshot(outside, outside / "none")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "symbolic link" in err and "rm " in err
    assert snapshot(outside, outside / "none") == before
    assert (outside / "victim.txt").read_text() == "precious\n"
    assert subjects(vault) == ["Initialize vault"]


def test_symlink_created_under_git_just_before_the_commit_is_refused(
    vg, vault, tmp_path, capsys, monkeypatch
):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "victim.txt").write_text("precious\n")
    real_scan = vg.scan_diff

    def scan_then_link(*args, **kwargs):
        result = real_scan(*args, **kwargs)
        (vault / ".git" / "COMMIT_EDITMSG").unlink(missing_ok=True)
        (vault / ".git" / "COMMIT_EDITMSG").symlink_to(outside / "victim.txt")
        return result

    monkeypatch.setattr(vg, "scan_diff", scan_then_link)
    (vault / "a.md").write_text("x\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "symbolic link" in err
    assert (outside / "victim.txt").read_text() == "precious\n"
    assert subjects(vault) == ["Initialize vault"]


def _conflict(vault):
    git(vault, "checkout", "-q", "-b", "side")
    (vault / "README.md").write_text("side\n")
    git(vault, "commit", "-q", "-am", "side")
    git(vault, "checkout", "-q", "main")
    (vault / "README.md").write_text("main\n")
    git(vault, "commit", "-q", "-am", "main change")


def test_merge_in_progress_is_refused(vg, vault, capsys):
    _conflict(vault)
    git(vault, "merge", "side", check=False)
    assert (vault / ".git" / "MERGE_HEAD").exists()
    before = (head(vault), index_bytes(vault))
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "merge" in err and "merge --abort" in err
    assert f"git -C '{vault}'" in err and err.count("\n") == 1
    assert (head(vault), index_bytes(vault)) == before


@pytest.mark.parametrize("marker,word,command", [
    ("CHERRY_PICK_HEAD", "cherry-pick", "cherry-pick --abort"),
    ("REVERT_HEAD", "revert", "revert --abort"),
    ("rebase-merge", "rebase", "rebase --abort"),
    ("rebase-apply", "rebase", "rebase --abort"),
])
def test_other_operations_in_progress_are_refused(vg, vault, capsys, marker, word, command):
    target = vault / ".git" / marker
    if marker.startswith("rebase"):
        target.mkdir()
    else:
        target.write_text(head(vault) + "\n")
    (vault / "a.md").write_text("x\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and word in err and command in err
    assert subjects(vault) == ["Initialize vault"]


def test_unmerged_paths_are_refused(vg, vault, capsys):
    _conflict(vault)
    git(vault, "merge", "side", check=False)
    (vault / ".git" / "MERGE_HEAD").unlink()  # unmerged paths without a merge state
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "unmerged" in err and "reset --merge" in err
    assert subjects(vault)[0] == "main change"


def test_detached_head_is_refused(vg, vault, capsys):
    git(vault, "checkout", "-q", "--detach")
    (vault / "a.md").write_text("x\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "detached" in err and "switch main" in err


@pytest.mark.parametrize("with_commit", [False, True])
def test_nested_repository_is_refused(vg, vault, capsys, with_commit):
    nested = make_repo(vault / "projects" / "inner", commit=with_commit)
    (nested / "file.md").write_text("x\n")
    (vault / "a.md").write_text("x\n")
    before = (head(vault), index_bytes(vault))
    for argv in (["commit-eod", TODAY], ["stage"]):
        code, _, err = run(vg, capsys, *argv)
        assert code == 1 and "nested git repository" in err and "projects/inner" in err
    assert (head(vault), index_bytes(vault)) == before


def test_nested_git_file_is_refused(vg, vault, capsys):
    (vault / "sub").mkdir()
    (vault / "sub" / ".git").write_text("gitdir: /nowhere\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and "nested git repository" in err


def test_same_day_amend_that_would_be_empty_is_nothing_to_commit(vg, vault, capsys):
    (vault / "a.md").write_text("x\n")
    assert run(vg, capsys, "commit-eod", TODAY)[0] == 0
    before = head(vault)
    (vault / "a.md").unlink()  # everything changed today is undone
    code, out, err = run(vg, capsys, "commit-eod", TODAY)
    assert (code, err) == (0, "")
    assert out.startswith("nothing to commit")
    assert head(vault) == before


def test_change_that_vanishes_after_the_status_check_is_nothing_to_commit(
    vg, vault, capsys, monkeypatch
):
    """The race between `status` and `add -A`: the change is undone in between."""
    (vault / "a.md").write_text("x\n")
    real_run = vg.Repo.run

    def undo_before_add(self, args, *a, **k):
        if args[:1] == ["add"]:
            (vault / "a.md").unlink()
        return real_run(self, args, *a, **k)

    monkeypatch.setattr(vg.Repo, "run", undo_before_add)
    code, out, _ = run(vg, capsys, "commit-eod", TODAY)
    assert code == 0 and out.startswith("nothing to commit")
    assert subjects(vault) == ["Initialize vault"]


# ========================================================= messages, output


def test_stale_index_lock_names_the_command(vg, vault, capsys):
    (vault / ".git" / "index.lock").write_text("")
    (vault / "a.md").write_text("x\n")
    code, _, err = run(vg, capsys, "stage")
    assert code == 1 and err.count("\n") == 1
    assert "no git process is running" in err
    assert f"rm '{vault}/.git/index.lock'" in err


def test_status_works_while_index_lock_exists(vg, vault, capsys):
    (vault / ".git" / "index.lock").write_text("")
    (vault / "a.md").write_text("x\n")
    code, out, err = run(vg, capsys, "status")
    assert (code, err) == (0, "") and "a.md" in out


def test_denied_config_names_the_unset_command(vg, vault, tmp_path, capsys):
    _local_config(vault, '[filter "x"]\n\tclean = cat\n')
    code, _, err = run(vg, capsys, "status")
    assert code == 1 and f"git -C '{vault}' config --unset-all filter.x.clean" in err


def test_remote_refusal_names_the_remove_command(vg, vault, capsys):
    git(vault, "remote", "add", "origin", "/nowhere")
    (vault / "a.md").write_text("x\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and f"git -C '{vault}' remote remove origin" in err


def test_missing_identity_names_the_config_command(vg, vault, capsys):
    git(vault, "config", "--unset", "user.email")
    (vault / "a.md").write_text("x\n")
    code, _, err = run(vg, capsys, "commit-eod", TODAY)
    assert code == 1 and f"git -C '{vault}' config user.email" in err


STATUS_CAP = 256 * 1024


def test_status_output_is_capped_at_256_kib(vg, vault, capsys):
    for i in range(3000):
        (vault / f"{'n' * 90}-{i:05d}.md").write_text("x")
    code, out, _ = run(vg, capsys, "status")
    assert code == 0
    body, _, last = out.rstrip("\n").rpartition("\n")
    assert last.startswith("[truncated:")
    assert len((body + "\n").encode()) <= STATUS_CAP
    assert len((body + "\n").encode()) > STATUS_CAP - 200


def test_staged_diff_cap_is_256_kib(vg, vault, capsys):
    (vault / "big.md").write_text("line of text\n" * 60000)
    git(vault, "add", "-A")
    code, out, _ = run(vg, capsys, "staged-diff")
    body, _, last = out.rstrip("\n").rpartition("\n")
    assert last.startswith("[truncated:") and str(STATUS_CAP) in last
    assert STATUS_CAP - 200 < len((body + "\n").encode()) <= STATUS_CAP


def test_staged_diff_names_section(vg, vault, capsys):
    (vault / "README.md").write_text("changed\n")
    (vault / "new note.md").write_text("x\n")
    (vault / "a\tb.md").write_text("y\n")
    git(vault, "add", "-A")
    code, out, _ = run(vg, capsys, "staged-diff")
    names, _, diff = out.partition("\n\n")
    assert names.split("\n") == ["M\tREADME.md", 'A\t"a\\tb.md"', "A\tnew note.md"]
    assert diff.startswith("diff --git ")


def test_c1_and_bidi_characters_are_escaped(vg, vault, capsys):
    (vault / "a\u202eb\u0085c\u009bd.md").write_text("x\n")
    code, out, _ = run(vg, capsys, "status")
    assert code == 0
    for ch in "\u202e\u0085\u009b":
        assert ch not in out
    assert "\\u202e" in out
    git(vault, "add", "-A")
    out = run(vg, capsys, "staged-diff")[1]
    assert not any(ch in out for ch in "\u202e\u0085\u009b")


def test_remote_output_is_escaped(vg, vault, capsys):
    (vault / ".git" / "remotes").mkdir()
    (vault / ".git" / "remotes" / "a\x1bb\u202ec").write_text("URL: /nowhere\n")
    code, out, _ = run(vg, capsys, "remote")
    assert code == 0
    assert out == "a\\x1bb\\u202ec\n"


def test_os_error_is_a_one_line_refusal(vg, vault, capsys, monkeypatch):
    def broken(*a, **k):
        raise PermissionError(13, "Permission denied", "/somewhere")

    monkeypatch.setattr(vg, "_walk_git_dir", broken)
    code, out, err = run(vg, capsys, "status")
    assert code == 1 and out == ""
    assert err.startswith("refused: ") and err.count("\n") == 1
    assert "Permission denied" in err and "Traceback" not in err


# ============================================= review round 2: path checks


@pytest.mark.parametrize("part", ["DOCUME~1", "a~2b", "~1"])
def test_short_name_component_is_refused(vg, home, tmp_path, capsys, monkeypatch, part):
    err = _refused(vg, capsys, monkeypatch, tmp_path / part / "vault")
    assert "short-name" in err


def _mountinfo(*mounts):
    lines = ["20 1 8:1 / / rw - ext4 /dev/sda1 rw"]
    for n, (point, tail) in enumerate(mounts):
        escaped = str(point).replace(" ", "\\040")
        lines.append(f"{100 + n} 20 0:{50 + n} / {escaped} rw - {tail}")
    return "\n".join(lines) + "\n"


C_TAIL = r"9p C:\134 rw,dirsync,aname=drvfs;path=C:\;uid=1000"
D_TAIL = r"9p D:\134 rw,dirsync,aname=drvfs;path=D:\;uid=1000"


def test_vault_on_another_mount_of_drive_c_is_refused(vg, vault, capsys, monkeypatch):
    text = _mountinfo((vault.parent, C_TAIL))
    monkeypatch.setattr(vg, "_read_mountinfo", lambda: text)
    assert "drive C" in _refused(vg, capsys, monkeypatch, vault)


def test_old_style_drvfs_mount_of_c_is_refused(vg, vault, capsys, monkeypatch):
    text = _mountinfo((vault.parent, r"drvfs C:\134 rw"))
    monkeypatch.setattr(vg, "_read_mountinfo", lambda: text)
    assert "drive C" in _refused(vg, capsys, monkeypatch, vault)


def test_vault_on_drive_d_mount_is_accepted(vg, vault, capsys, monkeypatch):
    text = _mountinfo((vault.parent, D_TAIL))
    monkeypatch.setattr(vg, "_read_mountinfo", lambda: text)
    assert run(vg, capsys, "status")[0] == 0


def test_unreadable_mountinfo_is_refused(vg, vault, capsys, monkeypatch):
    def broken():
        raise OSError("no /proc")

    monkeypatch.setattr(vg, "_read_mountinfo", broken)
    assert "mount" in _refused(vg, capsys, monkeypatch, vault)


def test_real_vault_through_a_second_mount_of_its_drive_is_refused_in_test_mode(
    vg, home, tmp_path, capsys, monkeypatch
):
    """Two mount points of D: show one directory under two names that samefile
    cannot match (each mount has its own device number)."""
    mount_a, mount_b = tmp_path / "mnt-a", tmp_path / "mnt-b"
    real = make_repo(mount_a / VAULT_NAME)
    alias = make_repo(mount_b / VAULT_NAME)
    monkeypatch.setattr(vg, "DEFAULT_VAULT", str(real))
    text = _mountinfo((mount_a, D_TAIL), (mount_b, D_TAIL))
    monkeypatch.setattr(vg, "_read_mountinfo", lambda: text)
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    monkeypatch.setenv("SECOND_BRAIN_TODAY", TODAY)
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(alias))
    code, _, err = run(vg, capsys, "status")
    assert code == 1 and "real vault" in err
