"""Unit tests for the command scenario harness (conftest.py).

These run in the default suite and never call the real `claude`; where a
process is needed, a small fake executable stands in for it.
"""

import json
import re
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

GOLDEN_BASELINE_SIZE = 19  # lines `python -m vault.conformance` prints on the unmodified golden vault
SESSION_ID = "11111111-2222-3333-4444-555555555555"

INIT_EVENT = {
    "type": "system",
    "subtype": "init",
    "cwd": "/tmp/x/work",
    "session_id": SESSION_ID,
    "tools": ["Bash", "Edit", "Read", "Skill", "Write"],
    "mcp_servers": [],
    "slash_commands": ["capture", "triage", "compact"],
    "permissionMode": "dontAsk",
}
ASSISTANT_EVENT = {
    "type": "assistant",
    "message": {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Writing the capture."},
            {"type": "tool_use", "id": "t1", "name": "Write", "input": {"file_path": "/tmp/x/vault/a.md", "content": "hi"}},
        ],
    },
    "session_id": SESSION_ID,
}
RESULT_EVENT = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "num_turns": 2,
    "result": "Captured to 00-Inbox.",
    "session_id": SESSION_ID,
    "total_cost_usd": 0.01,
    "permission_denials": [{"tool_name": "Bash", "tool_use_id": "t2", "tool_input": {"command": "rm -rf /"}}],
}
CANNED_STREAM = "\n".join(
    [json.dumps(INIT_EVENT), "Warning: not json", json.dumps(ASSISTANT_EVENT), "", json.dumps(RESULT_EVENT)]
)

# Every Bash allow rule the harness may ever grant, written out by hand.
APPROVED_COMMON_BASH = {
    "Bash(printenv SECOND_BRAIN_TEST_MODE SECOND_BRAIN_TODAY)",
    "Bash(printenv SECOND_BRAIN_VAULT)",
    "Bash(TZ=Asia/Manila date +%F)",
    "Bash(TZ=Asia/Manila date +%Y%m%d%H%M%S)",
    "Bash(TZ=Asia/Manila date +%H%M%S)",
    "Bash(date +%F)",
    "Bash(date +%Y%m%d%H%M%S)",
    "Bash(date +%H%M%S)",
    'Bash([ "$SECOND_BRAIN_VAULT" -ef "/mnt/d/Second Brain" ])',
    'Bash(test "$SECOND_BRAIN_VAULT" -ef "/mnt/d/Second Brain")',
    "Bash(echo *)",
}
APPROVED_BROWSE_BASH = {"Bash(ls)", "Bash(ls *)", "Bash(pwd)"}
VAULT_GIT_VERBS = ["remote", "status", "stage", "staged-diff", "head-subject", "commit-eod 2026-10-09"]


def approved_vault_git(ws):
    scripts = [str(ws.cwd / ".claude/skills/second-brain/scripts/vault_git.py"),
               ".claude/skills/second-brain/scripts/vault_git.py"]
    return {f"Bash(python3 -I {s} {verb})" for s in scripts for verb in VAULT_GIT_VERBS}


@pytest.fixture
def ws(hx, tmp_path):
    return hx.create_workspace(tmp_path)


def _fake_claude(tmp_path, body):
    script = tmp_path / "fake-claude"
    script.write_text(f"#!{sys.executable}\nimport json, os, sys, time\n{body}\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return str(script)


def _emit(*events):
    return "\n".join(f"print(json.dumps({e!r}), flush=True)" for e in events)


def _install_command(ws, name):
    folder = ws.claude_dir / "commands"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.md").write_text("stand-in\n")


# --- Workspace ---------------------------------------------------------------------------------


def test_workspace_vault_is_a_byte_identical_copy_of_the_fixture(hx, ws):
    assert hx.snapshot(ws.vault) == hx.snapshot(hx.FIXTURE_VAULT)


def test_workspace_vault_is_a_git_repo_with_an_isolated_identity(hx, ws):
    assert hx.git(ws, "config", "user.email").strip() == hx.GIT_IDENTITY[1]
    assert hx.git(ws, "log", "--format=%s %ae").strip() == f"fixture {hx.GIT_IDENTITY[1]}"
    assert hx.git(ws, "status", "--porcelain").strip() == ""
    assert hx.git(ws, "remote").strip() == ""
    assert ws.gitconfig.read_bytes() == b""


def test_workspace_paths_are_all_under_the_temporary_root(ws, tmp_path):
    root = tmp_path.resolve()
    for path in (ws.vault, ws.cwd, ws.home, ws.gitconfig, ws.settings_path("eod"), ws.claude_dir):
        assert path.is_relative_to(root)


def test_install_puts_the_skill_and_commands_in_the_workspace_or_reports_why_not(hx, ws):
    if sorted(hx.COMMANDS_SRC.glob("*.md")):
        assert ws.install_error is None
        assert (ws.claude_dir / "skills" / "second-brain" / "SKILL.md").is_file()
        assert ws.installed_commands() == sorted(p.stem for p in hx.COMMANDS_SRC.glob("*.md"))
    else:
        assert ws.install_error and "commands" in ws.install_error
        assert ws.installed_commands() == []
    assert not any(ws.home.iterdir()), "install.sh wrote into the fake HOME"


def test_install_fails_on_an_unexpected_error(hx, ws, tmp_path, monkeypatch):
    commands = tmp_path / "cmds"
    commands.mkdir()
    (commands / "capture.md").write_text("x\n")
    failing = tmp_path / "failing-install.sh"
    failing.write_text("echo boom >&2\nexit 3\n")
    monkeypatch.setattr(hx, "COMMANDS_SRC", commands)
    monkeypatch.setattr(hx, "INSTALL_SH", failing)
    with pytest.raises(AssertionError, match="install.sh failed: boom"):
        hx.install(ws)


# --- Isolation ---------------------------------------------------------------------------------


def test_isolation_accepts_paths_under_the_root(hx, tmp_path):
    (tmp_path / "v").mkdir()
    hx.check_isolation(tmp_path, tmp_path / "w", [tmp_path / "v"], {"SECOND_BRAIN_VAULT": str(tmp_path / "v")})


@pytest.mark.parametrize(
    "vault",
    ["/mnt/d/Second Brain", "/mnt/c/Users/User/Documents/Obsidian Vault", "/tmp", "relative/vault", ""],
)
def test_isolation_refuses_a_vault_outside_the_root(hx, tmp_path, vault):
    with pytest.raises(hx.IsolationError):
        hx.check_isolation(tmp_path, tmp_path / "w", [], {"SECOND_BRAIN_VAULT": vault})


def test_isolation_refuses_a_sibling_that_shares_the_roots_prefix(hx, tmp_path):
    root = tmp_path / "x"
    sibling = tmp_path / "x2"
    root.mkdir()
    sibling.mkdir()
    with pytest.raises(hx.IsolationError, match="outside the temporary root"):
        hx.check_isolation(root, root / "w", [], {"SECOND_BRAIN_VAULT": str(sibling)})
    assert not hx.contains(root, sibling)
    assert hx.contains(root, root / "w")


def test_isolation_refuses_a_symlink_that_leaves_the_root(hx, tmp_path, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    link = tmp_path / "vault"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(hx.IsolationError, match="outside the temporary root"):
        hx.check_isolation(tmp_path, tmp_path / "w", [], {"SECOND_BRAIN_VAULT": str(link)})


def test_isolation_refuses_a_working_directory_or_added_dir_outside_the_root(hx, tmp_path):
    with pytest.raises(hx.IsolationError, match="working directory"):
        hx.check_isolation(tmp_path, Path("/tmp"), [], {})
    with pytest.raises(hx.IsolationError, match="--add-dir"):
        hx.check_isolation(tmp_path, tmp_path / "w", [hx.REPO], {})


@pytest.mark.parametrize("root", ["repo", "user claude dir", "real vault other case", "old vault other case"])
def test_isolation_refuses_a_root_inside_a_protected_path(hx, root):
    path = {
        "repo": hx.REPO / "claude" / "tests",
        "user claude dir": hx.USER_CLAUDE_DIR / "tmp",
        "real vault other case": Path("/mnt/d/SECOND BRAIN/sub"),
        "old vault other case": Path("/mnt/c/users/user/documents/obsidian vault/x"),
    }[root]
    with pytest.raises(hx.IsolationError):
        hx.check_isolation(path, path / "w", [], {})


def test_protected_paths_compare_case_insensitively(hx):
    assert hx._overlaps_protected(Path("/mnt/d/second brain/notes")) == hx.REAL_VAULT
    assert hx._overlaps_protected(Path("/mnt")) == hx.REAL_VAULT  # a root above it overlaps too
    assert hx._overlaps_protected(Path("/tmp/elsewhere")) is None


def test_user_home_comes_from_the_password_database(hx, monkeypatch):
    import os
    import pwd

    assert hx.USER_HOME == Path(pwd.getpwuid(os.getuid()).pw_dir)
    assert hx.USER_CLAUDE_DIR == hx.USER_HOME / ".claude"


def test_isolation_refuses_a_root_with_whitespace(hx, tmp_path):
    root = tmp_path / "has space"
    with pytest.raises(hx.IsolationError, match="whitespace"):
        hx.check_isolation(root, root / "w", [], {})


def _no_popen(monkeypatch):
    launched = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: launched.append(a))
    return launched


def test_run_claude_refuses_before_launching_anything(hx, ws, monkeypatch):
    launched = _no_popen(monkeypatch)
    ws.vault = Path("/mnt/d/Second Brain")
    with pytest.raises(hx.IsolationError):
        hx.run_claude(ws, "/capture x", hx.HarnessConfig())
    assert launched == []


def test_run_claude_refuses_when_the_vault_is_a_symlink_out_of_the_root(hx, ws, tmp_path_factory, monkeypatch):
    launched = _no_popen(monkeypatch)
    outside = tmp_path_factory.mktemp("elsewhere")
    link = ws.root / "linked-vault"
    link.symlink_to(outside, target_is_directory=True)
    ws.vault = link
    with pytest.raises(hx.IsolationError):
        hx.run_claude(ws, "/capture x", hx.HarnessConfig())
    assert launched == []


def test_reply_checks_isolation_before_launching(hx, ws, monkeypatch):
    harness = hx.Harness(ws, hx.HarnessConfig())
    previous = hx.SessionResult(argv=[], prompt="/triage", events=[INIT_EVENT, RESULT_EVENT])
    ws.vault = Path("/mnt/d/Second Brain")
    launched = _no_popen(monkeypatch)
    monkeypatch.setattr(hx, "git_marks", lambda ws: ("h", b"i"))
    with pytest.raises(hx.IsolationError):
        harness.reply(previous, "yes")
    assert launched == []


# --- Permission profiles -----------------------------------------------------------------------


def _bash_rules(rules):
    return {r for r in rules if r.startswith("Bash(")}


def test_every_bash_allow_rule_is_in_the_approved_exact_set(hx, ws):
    approved = {
        "default": APPROVED_COMMON_BASH | APPROVED_BROWSE_BASH,
        "eod": APPROVED_COMMON_BASH | APPROVED_BROWSE_BASH | approved_vault_git(ws),
        "guard": APPROVED_COMMON_BASH,
    }
    for profile, expected in approved.items():
        allow = hx.permission_settings(ws, profile)["permissions"]["allow"]
        assert _bash_rules(allow) == expected, profile


def test_no_bash_allow_rule_runs_git_and_find_is_not_allowed(hx, ws):
    for profile in hx.PROFILES:
        for rule in _bash_rules(hx.permission_settings(ws, profile)["permissions"]["allow"]):
            command = rule[len("Bash("):-1]
            assert not re.match(r"\s*git\b", command), rule
            assert " git " not in f" {command} ", rule
            assert not command.startswith("find"), rule


def test_only_the_eod_profile_has_a_git_surface(hx, ws):
    for profile in ("default", "guard"):
        allow = hx.permission_settings(ws, profile)["permissions"]["allow"]
        assert not any("vault_git" in r for r in allow), profile
    eod = hx.permission_settings(ws, "eod")["permissions"]["allow"]
    vault_git = [r for r in eod if "vault_git" in r]
    assert set(vault_git) == approved_vault_git(ws)
    assert not any("*" in r for r in vault_git)


def test_guard_profile_has_no_write_tool_and_only_the_skill_shell_forms(hx, ws):
    rules = hx.permission_settings(ws, "guard")["permissions"]
    assert not any(r.startswith("Edit(") for r in rules["allow"])
    assert _bash_rules(rules["allow"]) == APPROVED_COMMON_BASH
    assert hx.TOOLS["guard"] == ("Read", "Bash", "Skill")
    argv = hx.build_argv(ws, "/capture x", hx.HarnessConfig(), profile="guard")
    assert argv[argv.index("--tools") + 1] == "Read,Bash,Skill"


def test_permissions_scope_writes_to_the_temporary_vault_and_deny_the_rest(hx, ws):
    for profile in ("default", "eod"):
        rules = hx.permission_settings(ws, profile)["permissions"]
        assert [r for r in rules["allow"] if r.startswith("Edit(")] == [f"Edit(/{ws.vault}/**)"]
        assert not {"Write", "Edit", "Bash"} & set(rules["allow"])
    rules = hx.permission_settings(ws, "eod")["permissions"]
    for protected in ("/mnt/d/Second Brain", "/mnt/c/Users/User/Documents/Obsidian Vault",
                      str(hx.USER_CLAUDE_DIR), str(hx.REPO)):
        assert f"Edit(/{protected}/**)" in rules["deny"]
        assert f"Read(/{protected}/**)" in rules["deny"]
    for rule in ("Bash(git)", "Bash(git *)", "Bash(*$(*)", "Bash(*`*)", "Bash(*<(*)", "Bash(*>(*)"):
        assert rule in rules["deny"]
    assert rules["disableBypassPermissionsMode"] == "disable"


def test_unknown_profile_is_refused(hx, ws):
    with pytest.raises(ValueError):
        hx.permission_settings(ws, "everything")


# --- Session environment -----------------------------------------------------------------------


def test_env_is_built_from_the_allowlist_only(hx, ws, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_MESSAGING_TOKEN", "fake-token-123")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
    monkeypatch.setenv("SECOND_BRAIN_VAULT", "/mnt/d/Second Brain")
    monkeypatch.setenv("GIT_DIR", "/elsewhere")
    monkeypatch.setenv("CLAUDE_CODE_SAFE_MODE", "1")
    env = hx.build_env(ws)
    assert set(env) <= hx.SESSION_ENV_ALLOWLIST
    assert "fake-token-123" not in env.values() and "ghp_fake" not in env.values()
    assert env["SECOND_BRAIN_VAULT"] == str(ws.vault)
    assert env["SECOND_BRAIN_TEST_MODE"] == "1"
    assert env["SECOND_BRAIN_TODAY"] == "2026-10-09"
    assert env["GIT_ALLOW_PROTOCOL"] == ""
    assert env["GIT_CONFIG_GLOBAL"] == str(ws.gitconfig)
    assert env["HOME"] == str(hx.USER_HOME)


def test_env_for_the_guard_leaves_the_vault_unset(hx, ws):
    env = hx.build_env(ws, vault_env=False, base={"SECOND_BRAIN_VAULT": "/mnt/d/Second Brain", "PATH": "/bin"})
    assert "SECOND_BRAIN_VAULT" not in env
    assert env["SECOND_BRAIN_TEST_MODE"] == "1"
    assert env["PATH"] == "/bin"


def test_the_session_process_sees_only_the_allowlisted_environment(hx, ws, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_ACCESS_TOKEN", "sekret-token")
    _install_command(ws, "capture")
    dump = tmp_path / "env.json"
    fake = _fake_claude(tmp_path, f"json.dump(dict(os.environ), open({str(dump)!r}, 'w'))\n"
                        + _emit(INIT_EVENT, RESULT_EVENT))
    session = hx.run_claude(ws, "/capture x", hx.HarnessConfig(claude_bin=fake), require_command="/capture")
    assert session.problem() is None, hx.describe(session)
    seen = json.loads(dump.read_text())
    assert "FAKE_ACCESS_TOKEN" not in seen
    assert set(seen) - {"PWD", "SHLVL", "_", "LC_CTYPE"} <= hx.SESSION_ENV_ALLOWLIST


# --- Invocation --------------------------------------------------------------------------------


def _flag(argv, name):
    return argv[argv.index(name) + 1]


def test_argv_puts_the_prompt_right_after_print_flag(hx, ws):
    argv = hx.build_argv(ws, "/capture buy oil", hx.HarnessConfig())
    assert argv[:3] == ["claude", "-p", "/capture buy oil"]


def test_argv_carries_the_isolation_and_cost_flags(hx, ws):
    config = hx.HarnessConfig(max_turns=7, max_budget_usd="0.50")
    argv = hx.build_argv(ws, "/daily", config)
    assert _flag(argv, "--output-format") == "stream-json"
    assert "--verbose" in argv
    assert _flag(argv, "--setting-sources") == "project"
    assert "--strict-mcp-config" in argv
    assert _flag(argv, "--permission-mode") == "dontAsk"
    assert _flag(argv, "--tools") == "Read,Write,Edit,Bash,Skill"
    assert _flag(argv, "--settings") == str(ws.settings_path("default"))
    assert _flag(argv, "--max-turns") == "7"
    assert _flag(argv, "--max-budget-usd") == "0.50"
    assert _flag(argv, "--add-dir") == str(ws.vault)
    assert "--model" not in argv and "--resume" not in argv
    assert not any("dangerously" in a or a == "bypassPermissions" for a in argv)


def test_argv_passes_the_allowlist_again_on_resume_and_sets_the_model(hx, ws):
    argv = hx.build_argv(ws, "yes", hx.HarnessConfig(model="haiku"), profile="eod", resume="abc")
    assert _flag(argv, "--resume") == "abc"
    assert _flag(argv, "--model") == "haiku"
    allow = hx.permission_settings(ws, "eod")["permissions"]["allow"]
    start = argv.index("--allowedTools") + 1
    assert argv[start : start + len(allow)] == allow


def test_config_reads_the_environment(hx):
    config = hx.HarnessConfig.from_env(
        {"SB_COMMANDS_MODEL": "sonnet", "SB_COMMANDS_TIMEOUT": "30", "SB_COMMANDS_MAX_TURNS": "5",
         "SB_COMMANDS_MAX_BUDGET_USD": "0.25", "SB_COMMANDS_CLAUDE_BIN": "/bin/fake"}
    )
    assert config == hx.HarnessConfig("/bin/fake", "sonnet", 30.0, 5, "0.25")
    assert hx.HarnessConfig.from_env({}) == hx.HarnessConfig()


@pytest.mark.parametrize("budget", ["0", "-1", "abc", "nan", "inf", "5.01", "100"])
def test_config_refuses_a_budget_that_is_not_a_positive_number_under_the_cap(hx, budget):
    with pytest.raises(ValueError):
        hx.HarnessConfig.from_env({"SB_COMMANDS_MAX_BUDGET_USD": budget})


def test_run_claude_writes_the_profiles_settings_file(hx, ws, tmp_path):
    fake = _fake_claude(tmp_path, _emit(INIT_EVENT, RESULT_EVENT))
    hx.run_claude(ws, "x", hx.HarnessConfig(claude_bin=fake), profile="guard")
    assert json.loads(ws.settings_path("guard").read_text()) == hx.permission_settings(ws, "guard")


# --- Output parsing ----------------------------------------------------------------------------


def test_parse_stream_reads_a_canned_claude_output(hx):
    session = hx.SessionResult(argv=[], prompt="/capture x", events=hx.parse_stream(CANNED_STREAM))
    assert len(session.events) == 3
    assert session.init["slash_commands"] == ["capture", "triage", "compact"]
    assert session.session_id == SESSION_ID
    assert session.text == "Captured to 00-Inbox."
    assert session.texts == ["Writing the capture.", "Captured to 00-Inbox."]
    assert "Writing the capture." in session.all_text
    assert session.tool_uses == [("Write", {"file_path": "/tmp/x/vault/a.md", "content": "hi"})]
    assert session.permission_denials[0]["tool_name"] == "Bash"
    assert session.problem() is None


@pytest.mark.parametrize(
    "result, problem",
    [
        (None, "no result event"),
        ({**RESULT_EVENT, "subtype": "error_max_turns", "is_error": True}, "error_max_turns"),
        ({**RESULT_EVENT, "is_error": True}, "is_error=True"),
    ],
)
def test_problem_reports_an_unusable_session(hx, result, problem):
    events = [INIT_EVENT] + ([result] if result else [])
    session = hx.SessionResult(argv=[], prompt="p", events=events, returncode=1)
    assert problem in session.problem()


def test_missing_command_reason_needs_both_the_installed_file_and_the_listing(hx, ws):
    # Listed (a same-named skill or built-in could be) but not installed: not found.
    reason = hx.missing_command_reason(INIT_EVENT, "/capture", ws)
    assert reason.startswith("command not found: /capture")
    _install_command(ws, "capture")
    assert hx.missing_command_reason(INIT_EVENT, "/capture", ws) is None
    _install_command(ws, "daily")  # installed but not listed
    reason = hx.missing_command_reason(INIT_EVENT, "/daily", ws)
    assert "claude/commands/daily.md" in reason and "did not list" in reason


def test_describe_includes_every_text_block_and_the_denials(hx):
    session = hx.SessionResult(argv=[], prompt="/capture x", events=hx.parse_stream(CANNED_STREAM))
    text = hx.describe(session)
    assert "Writing the capture." in text and "Captured to 00-Inbox." in text
    assert "rm -rf /" in text
    assert SESSION_ID in text


def test_paths_outside_the_root(hx, tmp_path):
    inside = f"{tmp_path}/vault/a.md"
    text = f'cat "{inside}" /mnt/d/Second Brain/x {tmp_path}2/y'
    outside = hx.paths_outside(text, tmp_path)
    assert inside not in outside
    assert "/mnt/d/Second" in outside
    assert f"{tmp_path}2/y" in outside


# --- Running a fake claude ---------------------------------------------------------------------


def test_run_claude_stops_a_session_whose_command_is_missing(hx, ws, tmp_path):
    fake = _fake_claude(tmp_path, f"{_emit(INIT_EVENT)}\ntime.sleep(60)")
    start = time.monotonic()
    session = hx.run_claude(ws, "/daily", hx.HarnessConfig(claude_bin=fake, timeout=30), require_command="/daily")
    assert time.monotonic() - start < 20
    assert session.aborted.startswith("command not found: /daily")
    assert session.problem().startswith("command not found")


def test_run_claude_collects_a_complete_session(hx, ws, tmp_path):
    _install_command(ws, "capture")
    fake = _fake_claude(tmp_path, f"assert os.getcwd() == {str(ws.cwd)!r}\n"
                        f"assert os.environ['SECOND_BRAIN_VAULT'] == {str(ws.vault)!r}\n"
                        + _emit(INIT_EVENT, ASSISTANT_EVENT, RESULT_EVENT))
    session = hx.run_claude(ws, "/capture x", hx.HarnessConfig(claude_bin=fake), require_command="/capture")
    assert session.problem() is None, hx.describe(session)
    assert session.returncode == 0
    assert session.text == "Captured to 00-Inbox."


def test_run_claude_times_out(hx, ws, tmp_path):
    fake = _fake_claude(tmp_path, "time.sleep(60)")
    start = time.monotonic()
    session = hx.run_claude(ws, "/daily", hx.HarnessConfig(claude_bin=fake, timeout=1))
    assert time.monotonic() - start < 20
    assert session.timed_out
    assert session.problem() == "the claude call timed out"


def test_kill_stops_the_whole_process_group(hx, ws, tmp_path):
    pidfile = tmp_path / "child.pid"
    fake = _fake_claude(
        tmp_path,
        f"import subprocess\np = subprocess.Popen(['sleep', '120'])\nopen({str(pidfile)!r}, 'w').write(str(p.pid))\n"
        + _emit(INIT_EVENT, RESULT_EVENT),
    )
    hx.run_claude(ws, "x", hx.HarnessConfig(claude_bin=fake))
    child = int(pidfile.read_text())
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            state = Path(f"/proc/{child}/stat").read_text().split()[2]
        except FileNotFoundError:
            break
        if state == "Z":
            break
        time.sleep(0.1)
    else:
        pytest.fail(f"child {child} of the session is still running")


def test_run_claude_reports_a_wait_that_hangs(hx, ws, tmp_path, monkeypatch):
    fake = _fake_claude(tmp_path, _emit(INIT_EVENT, RESULT_EVENT))
    real_popen = subprocess.Popen

    class HangingPopen(real_popen):
        def wait(self, timeout=None):
            if timeout == 30:
                raise subprocess.TimeoutExpired(self.args, timeout)
            return super().wait(timeout)

    monkeypatch.setattr(subprocess, "Popen", HangingPopen)
    session = hx.run_claude(ws, "x", hx.HarnessConfig(claude_bin=fake))
    assert "TimeoutExpired" in session.problem()
    assert "harness error" in hx.describe(session)


# --- Harness.run and Harness.reply -------------------------------------------------------------


def test_run_requires_the_command(hx, ws, tmp_path):
    fake = _fake_claude(tmp_path, _emit(INIT_EVENT, RESULT_EVENT))
    harness = hx.Harness(ws, hx.HarnessConfig(claude_bin=fake))
    with pytest.raises(pytest.fail.Exception, match="command not found: /daily"):
        harness.run("/daily")


def test_reply_resumes_the_same_session(hx, ws, tmp_path):
    fake = _fake_claude(tmp_path, f"assert sys.argv[sys.argv.index('--resume') + 1] == {SESSION_ID!r}\n"
                        + _emit(INIT_EVENT, RESULT_EVENT))
    harness = hx.Harness(ws, hx.HarnessConfig(claude_bin=fake))
    previous = hx.SessionResult(argv=[], prompt="/triage", events=[INIT_EVENT, RESULT_EVENT])
    assert harness.reply(previous, "yes").session_id == SESSION_ID


def test_reply_fails_when_the_session_id_changes(hx, ws, tmp_path):
    other = {**RESULT_EVENT, "session_id": "99999999-0000-0000-0000-000000000000"}
    fake = _fake_claude(tmp_path, _emit({**INIT_EVENT, "session_id": other["session_id"]}, other))
    harness = hx.Harness(ws, hx.HarnessConfig(claude_bin=fake))
    previous = hx.SessionResult(argv=[], prompt="/triage", events=[INIT_EVENT, RESULT_EVENT])
    with pytest.raises(pytest.fail.Exception, match="different session"):
        harness.reply(previous, "yes")


def test_reply_without_resume_support_fails(hx, ws, tmp_path):
    # A claude that ignores --resume would start a new session: caught by the id check.
    fake = _fake_claude(tmp_path, "assert '--resume' in sys.argv\n" + _emit(INIT_EVENT, RESULT_EVENT))
    harness = hx.Harness(ws, hx.HarnessConfig(claude_bin=fake))
    previous = hx.SessionResult(argv=[], prompt="/triage", events=[INIT_EVENT, RESULT_EVENT])
    harness.reply(previous, "yes")  # passes only because --resume was sent
    argv = hx.build_argv(ws, "yes", hx.HarnessConfig(), resume=SESSION_ID)
    assert "--resume" in argv


def _committing_fake(tmp_path, ws, init, *git_args):
    """A fake session that runs git in the vault, as a misbehaving command would."""
    body = (f"import subprocess\nsubprocess.run(['git', '-C', {str(ws.vault)!r}, *{list(git_args)!r}], check=True,"
            f" env={{'PATH': os.environ['PATH'], 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}})\n")
    return _fake_claude(tmp_path, body + _emit(init, RESULT_EVENT))


def test_run_fails_when_a_non_eod_session_commits(hx, ws, tmp_path):
    _install_command(ws, "capture")
    fake = _committing_fake(tmp_path, ws, INIT_EVENT, "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-q",
                            "--allow-empty", "-m", "sneaky")
    harness = hx.Harness(ws, hx.HarnessConfig(claude_bin=fake))
    with pytest.raises(pytest.fail.Exception, match="HEAD moved"):
        harness.run("/capture", "x")


def test_run_fails_when_a_non_eod_session_stages(hx, ws, tmp_path):
    _install_command(ws, "capture")
    (ws.vault / "new.md").write_text("x\n")
    fake = _committing_fake(tmp_path, ws, INIT_EVENT, "add", "new.md")
    harness = hx.Harness(ws, hx.HarnessConfig(claude_bin=fake))
    with pytest.raises(pytest.fail.Exception, match="index changed"):
        harness.run("/capture", "x")


def test_eod_scenarios_may_commit(hx, ws, tmp_path):
    _install_command(ws, "eod")
    fake = _committing_fake(tmp_path, ws, {**INIT_EVENT, "slash_commands": ["eod"]}, "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-q",
                            "--allow-empty", "-m", "eod: 2026-10-09")
    harness = hx.Harness(ws, hx.HarnessConfig(claude_bin=fake), profile="eod")
    harness.allow_git_writes = True
    harness.run("/eod")
    assert harness.git("log", "-1", "--format=%s").strip() == "eod: 2026-10-09"


# --- Planted git configuration -----------------------------------------------------------------


def test_harness_git_refuses_after_planted_config(hx, ws, tmp_path):
    marker = tmp_path / "ran"
    with open(ws.vault / ".git" / "config", "a") as config:
        config.write(f"[alias]\n\tst = !touch {marker}\n")
    with pytest.raises(hx.GitTamperError, match="config"):
        hx.git(ws, "status")
    assert not marker.exists()


def test_harness_git_refuses_after_a_planted_hook(hx, ws):
    hook = ws.vault / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 0\n")
    with pytest.raises(hx.GitTamperError, match="hooks"):
        hx.git(ws, "status")


def test_harness_git_refuses_after_a_planted_global_config(hx, ws):
    ws.gitconfig.write_text("[core]\n\tpager = touch /tmp/x\n")
    with pytest.raises(hx.GitTamperError, match="global git config"):
        hx.git(ws, "status")


def test_run_fails_the_test_when_the_session_plants_git_config(hx, ws, tmp_path):
    _install_command(ws, "capture")
    fake = _committing_fake(tmp_path, ws, INIT_EVENT, "config", "core.pager", "touch /tmp/never")
    harness = hx.Harness(ws, hx.HarnessConfig(claude_bin=fake))
    with pytest.raises(pytest.fail.Exception, match="config changed outside the harness"):
        harness.run("/capture", "x")


def test_harness_git_pins_hooks_pager_and_transport_off(hx, ws):
    argv = hx.git_argv(ws, "status")
    for item in ("core.hooksPath=/dev/null", "core.fsmonitor=false", "core.pager=cat", "diff.external="):
        assert item in argv
    assert "--no-pager" in argv
    env = hx.git_env(ws)
    assert env["GIT_ALLOW_PROTOCOL"] == "" and env["HOME"] == str(ws.home)
    assert set(env) <= {"PATH", "LANG", "HOME", "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL",
                        "GIT_ALLOW_PROTOCOL", "GIT_TERMINAL_PROMPT"}


def test_harness_git_still_works_after_its_own_config_change(hx, ws):
    hx.git(ws, "remote", "add", "origin", str(ws.root / "nowhere.git"))
    assert hx.git(ws, "remote").split() == ["origin"]


# --- Snapshots and expectations ----------------------------------------------------------------


def test_snapshot_records_bytes_and_directories_but_not_the_top_git(hx, tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("x")
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "n.md").write_bytes(b"\xef\xbb\xbf---\r\n")
    assert hx.snapshot(tmp_path) == {"a/": None, "a/n.md": b"\xef\xbb\xbf---\r\n"}


def test_snapshot_includes_a_nested_git_directory(hx, tmp_path):
    (tmp_path / "sub" / ".git").mkdir(parents=True)
    (tmp_path / "sub" / ".git" / "HEAD").write_text("x")
    assert "sub/.git/HEAD" in hx.snapshot(tmp_path)


def test_diff_finds_added_removed_and_changed(hx):
    before = {"a.md": b"1", "b.md": b"2", "d/": None}
    after = {"a.md": b"1", "b.md": b"3", "c.md": b"4", "e/": None}
    diff = hx.diff_snapshots(before, after)
    assert diff.added == {"c.md", "e/"}
    assert diff.removed == {"d/"}
    assert diff.changed == {"b.md"}
    assert hx.diff_snapshots(before, dict(before)).empty


def test_match_changes_accepts_exact_and_pattern_expectations(hx):
    diff = hx.diff_snapshots({"x.md": b"1"}, {"x.md": b"2", "00-Inbox/2026-10-09 1412 Hi.md": b""})
    pattern = re.compile(r"00-Inbox/2026-10-09 (\d{4}) Hi\.md")
    found = hx.match_changes(diff, added=(pattern,), changed=("x.md",))
    assert found[pattern] == "00-Inbox/2026-10-09 1412 Hi.md"


@pytest.mark.parametrize(
    "expected, message",
    [
        ({}, "unexpected"),
        ({"changed": ("x.md", "y.md")}, "expected 'y.md', not found"),
        ({"changed": (re.compile(r".*\.md"),)}, "matched several"),
        ({"changed": ("x.md", re.compile(r"x\.md"), "z.md")}, "meets both"),
        ({"changed": ("x.md",), "optional_changed": ("x.md",)}, "meets both"),
    ],
)
def test_match_changes_rejects_anything_else(hx, expected, message):
    diff = hx.diff_snapshots({"x.md": b"1", "z.md": b"1"}, {"x.md": b"2", "z.md": b"2"})
    with pytest.raises(AssertionError, match=message):
        hx.match_changes(diff, **expected)


def test_optional_change_may_be_absent_but_takes_exact_paths_only(hx):
    diff = hx.diff_snapshots({"x.md": b"1"}, {"x.md": b"2"})
    assert hx.match_changes(diff, changed=("x.md",), optional_changed=("y.md",)) == {"x.md": "x.md"}
    with pytest.raises(TypeError):
        hx.match_changes(diff, optional_changed=(re.compile(r".*"),))
    with pytest.raises(AssertionError, match="unexpected"):
        hx.match_changes(hx.diff_snapshots({"x.md": b"1", "w.md": b"1"}, {"x.md": b"2", "w.md": b"2"}),
                         optional_changed=("x.md",))


def test_changes_and_unchanged_wrappers_fail_the_test(hx, ws):
    harness = hx.Harness(ws, hx.HarnessConfig())
    before = harness.snapshot()
    (ws.vault / "00-Inbox" / "extra.md").write_text("x\n")
    with pytest.raises(pytest.fail.Exception, match="unexpected"):
        harness.unchanged(before)
    with pytest.raises(pytest.fail.Exception, match="not found"):
        harness.changes(before, added=("00-Inbox/extra.md", "00-Inbox/other.md"))
    assert harness.changes(before, added=("00-Inbox/extra.md",)) == {"00-Inbox/extra.md": "00-Inbox/extra.md"}


# --- Checker baseline, templates and note checks -----------------------------------------------


def test_golden_baseline_is_the_known_findings(hx):
    baseline = hx.findings(hx.FIXTURE_VAULT)
    assert len(baseline) == GOLDEN_BASELINE_SIZE
    assert ("F2", "02-Work/Tasks/Task without status.md") in baseline


def test_new_findings_are_judged_against_the_baseline(hx, ws):
    baseline = hx.findings(ws.vault)
    assert hx.new_findings(baseline, hx.findings(ws.vault)) == set()
    (ws.vault / "02-Work/Tasks/No status here.md").write_text("---\ntype: task\nid: 20261009120000\n---\n")
    assert hx.new_findings(baseline, hx.findings(ws.vault)) == {("F2", "02-Work/Tasks/No status here.md")}


def test_a_new_code_on_an_already_flagged_path_is_a_new_finding(hx, ws):
    rel = "02-Work/Tasks/Check the ladder rungs.md"  # already F7
    baseline = hx.findings(ws.vault)
    path = ws.vault / rel
    path.write_text(path.read_text().replace("project:\n", "project: lighthouse-tour\n", 1))
    assert hx.new_findings(baseline, hx.findings(ws.vault)) == {("W5", rel)}


def test_template_shape_returns_keys_and_headings(hx):
    keys, heads = hx.template_shape(hx.FIXTURE_VAULT, "task")
    assert keys == ["type", "id", "status", "priority", "project", "created", "due", "tags"]
    assert heads == ["## Description", "## Notes", "## Links"]
    template = hx.template_frontmatter(hx.FIXTURE_VAULT, "task")
    assert template["status"] == "planned" and template["priority"] == "medium"
    assert template["project"] is None and template["due"] is None and template["tags"] == []


TASK = "02-Work/Tasks/A checked task.md"
GOOD_TASK = (
    "---\ntype: task\nid: 20261009101500\nstatus: planned\npriority: medium\nproject:\n"
    "created: 2026-10-09\ndue:\ntags: []\n---\n\n## Description\n\n## Notes\n\n## Links\n"
)


def _write_task(hx, ws, text):
    (ws.vault / TASK).write_text(text)
    return hx.Harness(ws, hx.HarnessConfig())


def test_check_new_note_accepts_a_note_rendered_from_the_template(hx, ws):
    harness = _write_task(hx, ws, GOOD_TASK)
    session = hx.SessionResult(argv=[], prompt="/task x")
    assert harness.check_new_note(TASK, "task", session, status="planned").status == "planned"


@pytest.mark.parametrize(
    "bad, message",
    [
        (GOOD_TASK.replace("status: planned\npriority: medium\n", "priority: medium\nstatus: planned\n"), "keys"),
        (GOOD_TASK.replace("id: 20261009101500", "id: 20261008101500"), "does not match"),
        (GOOD_TASK.replace("due:\n", "due: 2026-10-10\n"), "keep the template's"),
        (GOOD_TASK.replace("priority: medium", "priority: high"), "keep the template's"),
        (GOOD_TASK.replace("project:\n", 'project: "[[Harbor Lights]]"\n'), "keep the template's"),
        (GOOD_TASK.replace("## Notes\n\n", ""), "headings"),
        (GOOD_TASK.replace("created: 2026-10-09", "created: 2026-10-08"), "created"),
    ],
)
def test_check_new_note_rejects_a_wrong_note_and_prints_it(hx, ws, bad, message):
    harness = _write_task(hx, ws, bad)
    session = hx.SessionResult(argv=[], prompt="/task x")
    with pytest.raises(pytest.fail.Exception, match=message) as info:
        harness.check_new_note(TASK, "task", session)
    assert f"--- {TASK}" in str(info.value) and "type: task" in str(info.value)


def test_note_parsing_uses_the_project_parser(hx):
    note = hx.parse_note(hx.FIXTURE_VAULT, "02-Work/Tasks/Wire the dock lights.md")
    assert note.type == "task" and note.status == "in-progress" and note.project == "harbor-lights"
    assert note.frontmatter["project"] == "[[Harbor Lights|the harbor]]"


def test_emitted_link_is_folder_qualified_only_for_a_duplicated_stem(hx):
    assert hx.emitted_link(hx.FIXTURE_VAULT, "02-Work/Projects/Harbor Lights.md") == "[[Harbor Lights]]"
    assert (hx.emitted_link(hx.FIXTURE_VAULT, "02-Work/Projects/Lantern Festival.md")
            == "[[02-Work/Projects/Lantern Festival]]")


def test_section_items_match_the_untouched_scenario_expectation(hx):
    expected = json.loads((hx.CARRY_FORWARD / "untouched-note" / "scenario.json").read_text())
    text = (hx.CARRY_FORWARD / "untouched-note" / "expected.md").read_text()
    assert hx.section_items(text) == expected["expected_sections"]


def test_headings_skip_fenced_code(hx):
    assert hx.headings("## A\n```\n## not\n```\n### B ##\n") == ["## A", "### B"]


def test_heading_order_in_printed_text(hx):
    text = "Standup\n\n**Done:**\n- x\n## Today\n- y\nBlockers\nDecisions / Updates:\n### Follow-ups\nRelated Tasks / Projects"
    assert hx.heading_order_in_text(text, hx.STANDUP_HEADINGS) == list(hx.STANDUP_HEADINGS)


# --- Re-review follow-ups ------------------------------------------------------------------------


def _argv_recording_fake(tmp_path, record, init=INIT_EVENT):
    return _fake_claude(tmp_path, f"open({str(record)!r}, 'a').write(json.dumps(sys.argv) + '\\n')\n"
                        + _emit(init, RESULT_EVENT))


def _recorded(record):
    return [json.loads(line) for line in record.read_text().splitlines()]


def test_run_with_the_guard_profile_offers_no_write_tool_and_reply_keeps_it(hx, ws, tmp_path):
    _install_command(ws, "capture")
    record = tmp_path / "argv.jsonl"
    harness = hx.Harness(ws, hx.HarnessConfig(claude_bin=_argv_recording_fake(tmp_path, record)))
    first = harness.run("/capture", "x", profile="guard", vault_env=False)
    assert json.loads(ws.settings_path("guard").read_text()) == hx.permission_settings(ws, "guard")
    harness.reply(first, "yes")
    for argv in _recorded(record):
        assert argv[argv.index("--tools") + 1] == "Read,Bash,Skill"
        assert argv[argv.index("--settings") + 1] == str(ws.settings_path("guard"))


def test_reply_keeps_the_harness_profile_of_the_first_turn(hx, ws, tmp_path):
    _install_command(ws, "eod")
    record = tmp_path / "argv.jsonl"
    fake = _argv_recording_fake(tmp_path, record, {**INIT_EVENT, "slash_commands": ["eod"]})
    harness = hx.Harness(ws, hx.HarnessConfig(claude_bin=fake), profile="eod")
    first = harness.run("/eod")
    harness.profile = "default"  # a later change must not leak into turn 2 of the same session
    harness.reply(first, "no")
    for argv in _recorded(record):
        assert argv[argv.index("--settings") + 1] == str(ws.settings_path("eod"))


def test_check_new_note_rejects_a_given_value_that_differs(hx, ws):
    harness = _write_task(hx, ws, GOOD_TASK)
    session = hx.SessionResult(argv=[], prompt="/task x")
    with pytest.raises(pytest.fail.Exception, match="priority is 'medium', expected 'high'"):
        harness.check_new_note(TASK, "task", session, priority="high")


def test_kill_returns_promptly_when_a_child_holds_stdout(hx, ws, tmp_path):
    fake = _fake_claude(tmp_path, "import subprocess\nsubprocess.Popen(['sleep', '120'])\n" + _emit(INIT_EVENT, RESULT_EVENT))
    start = time.monotonic()
    session = hx.run_claude(ws, "x", hx.HarnessConfig(claude_bin=fake))
    assert time.monotonic() - start < 30
    assert session.problem() is None, hx.describe(session)


def test_a_code_absent_from_the_golden_baseline_is_a_new_finding(hx, ws):
    baseline = hx.findings(ws.vault)
    assert not any(code == "F6" for code, _ in baseline)
    (ws.vault / "08-System" / "Templates" / "task.md").unlink()
    assert {code for code, _ in hx.new_findings(baseline, hx.findings(ws.vault))} == {"F6"}


@pytest.mark.parametrize("where", ["refs/heads/evil", "hooks-dir-link", "info/exclude"])
def test_harness_git_refuses_a_symlink_anywhere_under_dot_git(hx, ws, tmp_path, where):
    target = tmp_path / "elsewhere"
    target.mkdir()
    link = ws.vault / ".git" / where
    if link.exists():
        link.unlink()
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(hx.GitTamperError, match="symbolic link"):
        hx.git(ws, "status")


def test_denials_outside_root_exempt_the_guards_exact_allowed_commands(hx, ws):
    guard_cmd = '[ "$SECOND_BRAIN_VAULT" -ef "/mnt/d/Second Brain" ]'
    session = hx.SessionResult(argv=[], prompt="p", events=[INIT_EVENT, {**RESULT_EVENT, "permission_denials": [
        {"tool_name": "Bash", "tool_input": {"command": guard_cmd}},
        {"tool_name": "Bash", "tool_input": {"command": f"{guard_cmd} && echo real"}},
        {"tool_name": "Read", "tool_input": {"file_path": "/mnt/d/Second Brain/x.md"}},
        {"tool_name": "Read", "tool_input": {"file_path": f"{ws.vault}/a.md"}},
    ]}])
    found = hx.denials_outside_root(session, ws, "guard")
    assert [d["command"] for d in found] == [f"{guard_cmd} && echo real", '{"file_path": "/mnt/d/Second Brain/x.md"}']
    assert all(d["paths"] for d in found)


def test_describe_shows_cost_and_denied_commands_in_full(hx):
    long_cmd = "python3 .claude/skills/second-brain/scripts/vault_git.py commit-eod 2026-10-09 2>&1; echo $? " + "x" * 400
    session = hx.SessionResult(argv=[], prompt="/eod", events=[INIT_EVENT, {**RESULT_EVENT, "total_cost_usd": 0.1234,
        "permission_denials": [{"tool_name": "Bash", "tool_input": {"command": long_cmd}}]}])
    text = hx.describe(session)
    assert "cost_usd=0.1234" in text
    assert long_cmd in text
    assert "allowed only as exact commands" in text


def test_run_claude_adds_the_session_cost_to_the_run_total(hx, ws, tmp_path, monkeypatch):
    monkeypatch.setattr(hx, "RUN_COSTS", [])
    fake = _fake_claude(tmp_path, _emit(INIT_EVENT, {**RESULT_EVENT, "total_cost_usd": 0.25}))
    hx.run_claude(ws, "x", hx.HarnessConfig(claude_bin=fake))
    hx.run_claude(ws, "y", hx.HarnessConfig(claude_bin=fake))
    assert hx.RUN_COSTS == [0.25, 0.25]
    assert "0.5000" in hx.cost_summary()
