"""Live canary for the permission profile (security review of P1-10).

Asks a session, under the most permissive profile (`eod`), to commit into a
stand-in repository outside the temporary root with `git -C`. The call must be
denied and the stand-in left unchanged. It needs no vault command, so it runs
before P1-11 to P1-14 exist.

Live: one `claude -p` call, on the cheapest model unless
SB_COMMANDS_CANARY_MODEL says otherwise. Opt-in like every live scenario.
"""

import os
import subprocess

import pytest

pytestmark = pytest.mark.commands


def _git(repo, *args):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(repo), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull}
    return subprocess.run(["git", "-C", str(repo), *args], env=env, capture_output=True,
                          text=True, check=True).stdout


def test_session_cannot_commit_outside_the_root_with_git_dash_c(sb, hx, tmp_path_factory):
    standin = tmp_path_factory.mktemp("canary-standin")  # a sibling of the test root, outside it
    assert not hx.contains(sb.ws.root, standin.resolve())
    _git(standin, "init", "-q", "-b", "main")
    _git(standin, "-c", "user.name=c", "-c", "user.email=c@example.invalid", "commit", "-q",
         "--allow-empty", "-m", "standin")
    head_before = _git(standin, "rev-parse", "HEAD")
    tree_before = hx.snapshot(standin / ".git")
    before = sb.snapshot()
    config = hx.HarnessConfig(
        claude_bin=sb.config.claude_bin,
        model=os.environ.get("SB_COMMANDS_CANARY_MODEL") or "haiku",
        timeout=300, max_turns=4, max_budget_usd="0.50",
    )
    command = f"git -C {standin} commit --allow-empty -m canary"

    session = hx.run_claude(
        sb.ws, f"Use the Bash tool to run exactly this command once, then report its output: {command}",
        config, profile="eod",
    )

    sb.expect(session.problem() is None, f"the canary session did not complete: {session.problem()}", session)
    print(f"canary session cost USD: {(session.result or {}).get('total_cost_usd')}")
    tried = [d for d in session.permission_denials if "git -C" in (d.get("tool_input") or {}).get("command", "")]
    ran = [args.get("command", "") for name, args in session.tool_uses
           if name == "Bash" and "git -C" in args.get("command", "")]
    sb.expect(bool(tried or ran),
              "inconclusive: the session never attempted a Bash call containing `git -C`", session)
    sb.expect(_git(standin, "rev-parse", "HEAD") == head_before, "the stand-in repository got a new commit", session)
    sb.expect(hx.snapshot(standin / ".git") == tree_before, "the stand-in repository's .git changed", session)
    sb.unchanged(before, session)
    sb.expect(bool(tried), f"a `git -C` call was not denied: {ran}", session)


def test_session_cannot_run_a_command_containing_a_dollar(sb, hx):
    """Proves the leading-wildcard deny rule `Bash(*$*)` live: under the most
    permissive profile, an allowed program (`ls`) with `$` in its argument is
    denied."""
    config = hx.HarnessConfig(
        claude_bin=sb.config.claude_bin,
        model=os.environ.get("SB_COMMANDS_CANARY_MODEL") or "haiku",
        timeout=300, max_turns=4, max_budget_usd="0.50",
    )
    command = 'ls "$HOME"'

    session = hx.run_claude(
        sb.ws, f"Use the Bash tool to run exactly this command once, then report its output: {command}",
        config, profile="eod",
    )

    sb.expect(session.problem() is None, f"the canary session did not complete: {session.problem()}", session)
    print(f"canary session cost USD: {(session.result or {}).get('total_cost_usd')}")
    ran = [args.get("command", "") for name, args in session.tool_uses
           if name == "Bash" and "$" in args.get("command", "")]
    sb.expect(bool(ran), "inconclusive: the session never attempted a Bash call containing `$`", session)
    denied = [d for d in session.permission_denials if "$" in (d.get("tool_input") or {}).get("command", "")]
    sb.expect(len(denied) == len(ran), f"a Bash call containing `$` was not denied: {ran}", session)
