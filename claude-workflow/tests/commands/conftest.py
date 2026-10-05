"""Headless harness for the vault command scenarios (task P1-10).

Each live scenario gets a throwaway world under pytest's `tmp_path`:

    <tmp>/vault/         a copy of second-brain/fixtures/golden-vault/vault, git-initialised
    <tmp>/work/          the session's working directory
    <tmp>/work/.claude/  the skill and commands, installed by claude-workflow/install.sh --target
    <tmp>/home/          HOME for install.sh and for the harness's own git calls
    <tmp>/gitconfig      GIT_CONFIG_GLOBAL (empty) for every git call

and runs `claude -p "/<command> <args>"` from <tmp>/work with the test clock of
plan section 2.12 and the permission profile of the scenario
(`permission_settings`). Scenarios assert on a byte snapshot of the vault taken
before and after, on HEAD and the git index (unchanged except in the /eod
scenarios, plan 4.1), on the conformance checker's findings relative to the
same baseline, and on note frontmatter parsed with web-app/backend/vault's own parser.

Safety (plan P1-10 amendments, sections 4.1 and 4.2):

- `check_isolation` runs before every launch, turn 2 included: the working
  directory, --add-dir and SECOND_BRAIN_VAULT must resolve under the test's
  temporary root, and the root must not overlap the real vault, the old vault,
  ~/.claude (home from the password database) or this repository.
- A session gets no `git` permission. Only the /eod profile may run the
  skill's `vault_git.py`, by exact rules, one per verb. Every Bash allow rule is
  an exact command or a program that can neither run another program nor write
  a file except through a redirection (which the Edit rules govern).
- The session environment is built from an allowlist (`SESSION_ENV_PASSTHROUGH`
  plus the values the harness sets); nothing else in this shell reaches it.
- Before the harness runs git itself it checks that the vault's `.git/config`
  is byte-identical to what the harness last left there, that `.git/hooks`
  holds only `*.sample` files and that the global git config is still empty;
  its git runs with hooks, fsmonitor, pager, external diff and transports off.

Live scenarios carry the `commands` marker and are excluded from the default
run by `addopts = ["-m", "not commands"]` in claude-workflow/pyproject.toml. Any other
`-m` expression given on the command line replaces that default and can select
the live scenarios: they launch `claude` and spend tokens.

Knobs, all optional environment variables:

    SB_COMMANDS_MODEL           --model for every session (default: account default)
    SB_COMMANDS_TIMEOUT         seconds per claude call (default 600)
    SB_COMMANDS_MAX_TURNS       --max-turns per call (default 40)
    SB_COMMANDS_MAX_BUDGET_USD  --max-budget-usd per call (default 2.00, at most 5.00)
    SB_COMMANDS_CLAUDE_BIN      the claude executable (default "claude")
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import pwd
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pytest

# --- Fixed locations and values ---------------------------------------------------------------

REPO = Path(__file__).resolve().parents[3]
FIXTURE = REPO / "second-brain" / "fixtures" / "golden-vault"
FIXTURE_VAULT = FIXTURE / "vault"
CARRY_FORWARD = FIXTURE / "expected" / "carry-forward"
INSTALL_SH = REPO / "claude-workflow" / "install.sh"
COMMANDS_SRC = REPO / "claude-workflow" / "commands"
BACKEND = REPO / "web-app" / "backend"

TODAY = "2026-10-09"  # the fixture's reference date (2.12)
TODAY_DATE = date(2026, 10, 9)
ID_RE = re.compile(r"^20261009[0-9]{6}$")  # an id written in test mode (fixture README)
DAILY_NOTE = "01-Daily/2026/2026-10-09.md"

REAL_VAULT = Path("/mnt/d/Second Brain")
OLD_VAULT = Path("/mnt/c/Users/User/Documents/Obsidian Vault")
USER_HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)  # not $HOME, which a caller can change
USER_CLAUDE_DIR = USER_HOME / ".claude"
# Paths no session may read or write; also the places a temp root must never overlap.
PROTECTED = (REAL_VAULT, OLD_VAULT, USER_CLAUDE_DIR, REPO)

STANDUP_HEADINGS = (
    "Done",
    "Today",
    "Blockers",
    "Decisions / Updates",
    "Follow-ups",
    "Related Tasks / Projects",
)

MAX_BUDGET_CAP_USD = 5.0

# --- Permission profiles -----------------------------------------------------------------------

PROFILES = ("default", "eod", "guard")
WRITE_TOOLS = ("Read", "Write", "Edit", "Bash", "Skill")
# The guard scenario is offered no file-writing tool at all.
READ_ONLY_TOOLS = ("Read", "Bash", "Skill")
TOOLS = {"default": WRITE_TOOLS, "eod": WRITE_TOOLS, "guard": READ_ONLY_TOOLS}

# A command learns the vault path, today's date and the clock from one
# observable call, `python3 -I <skill>/scripts/vault_git.py env` (plan 2.12,
# "Command sessions use one call"; 4.2). It is the only Bash command the guard
# profile allows: a session in the guard scenario runs it, sees `refused:` and
# stops. No printenv, date, `[`, `test` or echo rule exists in any profile.
# Listing folders: `ls` runs no other program. `find` is not allowed (-exec,
# -execdir, -ok, -okdir, -delete, -fprint, -fprintf, -fls); `ls` and Read suffice.
BROWSE_BASH_ALLOW = ("Bash(ls)", "Bash(ls *)", "Bash(pwd)")

ENV_VERB = "env"  # every profile
VAULT_GIT_VERBS = ("remote", "status", "stage", "staged-diff", "head-subject", f"commit-eod {TODAY}")  # eod only
VAULT_GIT_RELATIVE = ".claude/skills/second-brain/scripts/vault_git.py"

BASH_DENY = (
    "Bash(git)",
    "Bash(git *)",
    # Backstops: `ls *` is the one wildcard Bash rule left, and `ls $(cmd)`
    # must not run cmd. Kept although no allowed command needs them.
    "Bash(*$(*)",  # command substitution
    "Bash(*`*)",
    "Bash(*<(*)",  # process substitution
    "Bash(*>(*)",
)

# --- Session environment -----------------------------------------------------------------------

# Passed through from this shell when present. Claude Code authenticates a
# claude.ai login from the credentials file under HOME (or CLAUDE_CONFIG_DIR),
# so no token variable is passed; API-key users would need ANTHROPIC_API_KEY
# added here deliberately.
SESSION_ENV_PASSTHROUGH = ("PATH", "LANG", "TERM", "USER", "CLAUDE_CONFIG_DIR")
# Set by the harness.
SESSION_ENV_SET = (
    "HOME",
    "SECOND_BRAIN_TEST_MODE",
    "SECOND_BRAIN_TODAY",
    "SECOND_BRAIN_VAULT",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_ALLOW_PROTOCOL",
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY",
    "ENABLE_CLAUDEAI_MCP_SERVERS",
)
SESSION_ENV_ALLOWLIST = frozenset(SESSION_ENV_PASSTHROUGH + SESSION_ENV_SET)

GIT_IDENTITY = ("Second Brain Test", "second-brain-test@example.invalid")
# Pinned on every git call the harness makes.
GIT_SAFE_CONFIG = (
    "core.hooksPath=/dev/null",
    "core.fsmonitor=false",
    "core.pager=cat",
    "core.sshCommand=false",
    "credential.helper=",
    "diff.external=",
)


class IsolationError(RuntimeError):
    """A session would be able to reach something outside its temporary root."""


class GitTamperError(AssertionError):
    """The vault's git configuration or hooks changed behind the harness's back."""


# --- Configuration -----------------------------------------------------------------------------


@dataclass(frozen=True)
class HarnessConfig:
    claude_bin: str = "claude"
    model: str | None = None
    timeout: float = 600.0
    max_turns: int = 40
    max_budget_usd: str = "2.00"

    def __post_init__(self) -> None:
        try:
            budget = float(self.max_budget_usd)
        except ValueError as exc:
            raise ValueError(f"max budget is not a number: {self.max_budget_usd!r}") from exc
        if not (math.isfinite(budget) and 0 < budget <= MAX_BUDGET_CAP_USD):
            raise ValueError(f"max budget must be > 0 and <= {MAX_BUDGET_CAP_USD}: {self.max_budget_usd!r}")
        if not (self.timeout > 0 and self.max_turns > 0):
            raise ValueError("timeout and max turns must be positive")

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> HarnessConfig:
        env = os.environ if environ is None else environ
        return cls(
            claude_bin=env.get("SB_COMMANDS_CLAUDE_BIN") or "claude",
            model=env.get("SB_COMMANDS_MODEL") or None,
            timeout=float(env.get("SB_COMMANDS_TIMEOUT") or 600),
            max_turns=int(env.get("SB_COMMANDS_MAX_TURNS") or 40),
            max_budget_usd=env.get("SB_COMMANDS_MAX_BUDGET_USD") or "2.00",
        )


# --- Isolation ---------------------------------------------------------------------------------


def contains(parent: Path, child: Path, *, casefold: bool = False) -> bool:
    """True when `child` is `parent` or below it, by path components (never by
    string prefix: /tmp/x2 is not inside /tmp/x). Both should be resolved."""
    p_parts, c_parts = Path(parent).parts, Path(child).parts
    if casefold:
        p_parts = tuple(x.casefold() for x in p_parts)
        c_parts = tuple(x.casefold() for x in c_parts)
    return len(c_parts) >= len(p_parts) and c_parts[: len(p_parts)] == p_parts


def _overlaps_protected(path: Path) -> Path | None:
    # Case-insensitive: the Windows drives under /mnt are, so /mnt/d/second brain
    # is the real vault too.
    for protected in PROTECTED:
        p = protected.resolve()
        if contains(p, path, casefold=True) or contains(path, p, casefold=True):
            return protected
    return None


def check_isolation(root: Path, cwd: Path, add_dirs: list[Path], env: dict[str, str]) -> None:
    """Raise IsolationError unless everything a session can reach is under `root`.

    Paths are compared after resolving symlinks, so a link inside the root that
    points elsewhere is refused.
    """
    root_r = Path(root).resolve()
    if any(ch.isspace() for ch in str(root_r)):
        raise IsolationError(f"temporary root contains whitespace: {root_r}")
    hit = _overlaps_protected(root_r)
    if hit is not None:
        raise IsolationError(f"temporary root {root_r} overlaps protected path {hit}")
    named = {"working directory": Path(cwd), **{f"--add-dir {d}": Path(d) for d in add_dirs}}
    vault = env.get("SECOND_BRAIN_VAULT")
    if vault is not None:
        if not vault or not os.path.isabs(vault):
            raise IsolationError(f"SECOND_BRAIN_VAULT is not an absolute path: {vault!r}")
        named["SECOND_BRAIN_VAULT"] = Path(vault)
    for what, path in named.items():
        resolved = path.resolve()
        if not contains(root_r, resolved):
            raise IsolationError(f"{what} resolves to {resolved}, outside the temporary root {root_r}")
        hit = _overlaps_protected(resolved)
        if hit is not None:
            raise IsolationError(f"{what} resolves into protected path {hit}")


# --- Workspace and the harness's own git -------------------------------------------------------


@dataclass
class Workspace:
    root: Path
    vault: Path
    cwd: Path
    home: Path
    gitconfig: Path
    install_error: str | None = None
    git_config_bytes: bytes | None = None  # what the harness last left in .git/config

    @property
    def claude_dir(self) -> Path:
        return self.cwd / ".claude"

    def settings_path(self, profile: str) -> Path:
        return self.root / f"claude-settings-{profile}.json"

    def installed_commands(self) -> list[str]:
        folder = self.claude_dir / "commands"
        return sorted(p.stem for p in folder.glob("*.md")) if folder.is_dir() else []


def git_env(ws: Workspace) -> dict[str, str]:
    env = {k: os.environ[k] for k in ("PATH", "LANG") if k in os.environ}
    env.update(
        HOME=str(ws.home),
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=str(ws.gitconfig),
        GIT_ALLOW_PROTOCOL="",
        GIT_TERMINAL_PROMPT="0",
    )
    return env


def git_argv(ws: Workspace, *args: str) -> list[str]:
    pinned = [x for item in GIT_SAFE_CONFIG for x in ("-c", item)]
    return ["git", "--no-pager", *pinned, "-C", str(ws.vault), *args]


def verify_git_state(ws: Workspace) -> None:
    """Fail unless the vault's git setup is what the harness left: a session
    could otherwise plant configuration or hooks that the harness's git runs."""
    dot_git = ws.vault / ".git"
    if dot_git.is_symlink() or not dot_git.is_dir():
        raise GitTamperError(f"{dot_git} is no longer a plain directory")
    for dirpath, dirnames, filenames in os.walk(dot_git, followlinks=False):
        for name in dirnames + filenames:
            if (Path(dirpath) / name).is_symlink():
                raise GitTamperError(f"symbolic link under .git: {Path(dirpath, name).relative_to(ws.vault)}")
    if ws.git_config_bytes is None:
        raise GitTamperError("no recorded .git/config to compare with")
    if (dot_git / "config").read_bytes() != ws.git_config_bytes:
        raise GitTamperError(".git/config changed outside the harness:\n" + (dot_git / "config").read_text(errors="replace"))
    hooks = dot_git / "hooks"
    planted = sorted(p.name for p in hooks.iterdir() if not p.name.endswith(".sample")) if hooks.is_dir() else []
    if planted:
        raise GitTamperError(f".git/hooks holds non-sample files: {planted}")
    if ws.gitconfig.read_bytes() != b"":
        raise GitTamperError(f"the global git config {ws.gitconfig} is no longer empty")


def git(ws: Workspace, *args: str) -> str:
    if ws.git_config_bytes is not None:  # None only before `git init`
        verify_git_state(ws)
    proc = subprocess.run(
        git_argv(ws, *args), env=git_env(ws), stdin=subprocess.DEVNULL,
        capture_output=True, text=True, check=False,
    )
    ws.git_config_bytes = (ws.vault / ".git" / "config").read_bytes()
    if proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def git_marks(ws: Workspace) -> tuple[str, bytes]:
    """HEAD and the index bytes, to show a session did not stage or commit."""
    head_sha = git(ws, "rev-parse", "--verify", "-q", "HEAD").strip()
    index = ws.vault / ".git" / "index"
    return head_sha, (index.read_bytes() if index.exists() else b"")


def create_workspace(tmp_path: Path) -> Workspace:
    """Build the per-test world; nothing is launched here except git and install.sh."""
    root = Path(tmp_path).resolve()
    ws = Workspace(root=root, vault=root / "vault", cwd=root / "work", home=root / "home",
                   gitconfig=root / "gitconfig")
    check_isolation(root, ws.cwd, [ws.vault], {"SECOND_BRAIN_VAULT": str(ws.vault)})
    shutil.copytree(FIXTURE_VAULT, ws.vault, symlinks=True)
    ws.cwd.mkdir()
    ws.home.mkdir()
    ws.gitconfig.write_bytes(b"")

    git(ws, "init", "-q", "-b", "main")
    for key, value in (
        ("core.autocrlf", "false"),
        ("core.filemode", "false"),
        ("core.quotepath", "false"),
        ("commit.gpgsign", "false"),
        ("user.name", GIT_IDENTITY[0]),
        ("user.email", GIT_IDENTITY[1]),
    ):
        git(ws, "config", key, value)
    commit_all(ws, "fixture")

    ws.install_error = install(ws)
    return ws


def commit_all(ws: Workspace, message: str) -> str:
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "--allow-empty", "-m", message)
    return head(ws)


def head(ws: Workspace) -> str:
    return git(ws, "rev-parse", "HEAD").strip()


def install(ws: Workspace) -> str | None:
    """Run install.sh into <cwd>/.claude. Returns install.sh's error when the repo
    has no command files yet (P1-11 to P1-14 not done); any other failure is fatal."""
    target = ws.claude_dir
    check_isolation(ws.root, target, [], {})
    env = {k: os.environ[k] for k in ("PATH", "LANG") if k in os.environ}
    env["HOME"] = str(ws.home)
    proc = subprocess.run(
        ["bash", str(INSTALL_SH), "--target", str(target)],
        env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False,
    )
    if proc.returncode == 0:
        return None
    if not sorted(COMMANDS_SRC.glob("*.md")):
        return proc.stderr.strip() or f"install.sh exited {proc.returncode}"
    raise AssertionError(f"install.sh failed: {proc.stderr.strip()}")


# --- Claude invocation -------------------------------------------------------------------------


def _rule_path(path: Path) -> str:
    # Permission rules use //abs/path for an absolute filesystem path.
    return "/" + str(path)


def vault_git_rules(ws: Workspace, verbs: tuple[str, ...] = VAULT_GIT_VERBS) -> list[str]:
    """Exact rules for the skill's wrapper (plan 4.2), absolute and cwd-relative."""
    absolute = str(ws.cwd / VAULT_GIT_RELATIVE)
    return [f"Bash(python3 -I {script} {verb})" for script in (absolute, VAULT_GIT_RELATIVE) for verb in verbs]


def permission_settings(ws: Workspace, profile: str = "default") -> dict[str, Any]:
    """The --settings document: what a session of `profile` may do without asking."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}")
    allow = [f"Read({_rule_path(ws.root)}/**)"]
    if profile != "guard":
        allow.append(f"Edit({_rule_path(ws.vault)}/**)")
    allow.append("Skill")
    allow += vault_git_rules(ws, (ENV_VERB,))
    if profile != "guard":
        allow += BROWSE_BASH_ALLOW
    if profile == "eod":
        allow += vault_git_rules(ws)
    deny = [f"{tool}({_rule_path(p)}/**)" for p in PROTECTED for tool in ("Read", "Edit")]
    deny += BASH_DENY
    return {"permissions": {"allow": allow, "deny": deny, "disableBypassPermissionsMode": "disable"}}


def build_env(ws: Workspace, *, vault_env: bool = True, base: dict[str, str] | None = None) -> dict[str, str]:
    """The session environment, from an allowlist only."""
    source = os.environ if base is None else base
    env = {k: source[k] for k in SESSION_ENV_PASSTHROUGH if k in source}
    env.update(
        HOME=str(USER_HOME),  # the claude.ai login's credentials live under it
        SECOND_BRAIN_TEST_MODE="1",
        SECOND_BRAIN_TODAY=TODAY,
        GIT_CONFIG_GLOBAL=str(ws.gitconfig),
        GIT_CONFIG_NOSYSTEM="1",
        GIT_ALLOW_PROTOCOL="",
        CLAUDE_CODE_DISABLE_AUTO_MEMORY="1",
        ENABLE_CLAUDEAI_MCP_SERVERS="false",
    )
    if vault_env:
        env["SECOND_BRAIN_VAULT"] = str(ws.vault)
    return env


def build_argv(
    ws: Workspace,
    prompt: str,
    config: HarnessConfig,
    *,
    profile: str = "default",
    resume: str | None = None,
) -> list[str]:
    """The full claude command line. The prompt comes right after -p because
    --allowedTools and --add-dir take a variable number of values."""
    allow = permission_settings(ws, profile)["permissions"]["allow"]
    argv = [
        config.claude_bin, "-p", prompt,
        "--output-format", "stream-json", "--verbose",
        "--setting-sources", "project",
        "--strict-mcp-config",
        "--permission-mode", "dontAsk",
        "--tools", ",".join(TOOLS[profile]),
        "--settings", str(ws.settings_path(profile)),
        "--max-turns", str(config.max_turns),
        "--max-budget-usd", config.max_budget_usd,
        "--add-dir", str(ws.vault),
        "--allowedTools", *allow,
    ]
    if config.model:
        argv += ["--model", config.model]
    if resume:
        argv += ["--resume", resume]
    return argv


@dataclass
class SessionResult:
    argv: list[str]
    prompt: str
    events: list[dict[str, Any]] = field(default_factory=list)
    profile: str = "default"  # the permission profile; a resume keeps it
    stderr: str = ""
    returncode: int | None = None
    timed_out: bool = False
    aborted: str | None = None  # why the harness stopped the session early
    error: str | None = None  # an exception while collecting the session

    @property
    def init(self) -> dict[str, Any] | None:
        return next((e for e in self.events if e.get("type") == "system" and e.get("subtype") == "init"), None)

    @property
    def result(self) -> dict[str, Any] | None:
        return next((e for e in reversed(self.events) if e.get("type") == "result"), None)

    @property
    def session_id(self) -> str | None:
        for event in (self.result, self.init):
            if event and event.get("session_id"):
                return event["session_id"]
        return None

    @property
    def text(self) -> str:
        """The final result text."""
        return (self.result or {}).get("result") or ""

    @property
    def texts(self) -> list[str]:
        """Every assistant text block of the turn, then the result text."""
        out = []
        for event in self.events:
            if event.get("type") != "assistant":
                continue
            for item in (event.get("message") or {}).get("content") or []:
                if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                    out.append(item["text"])
        if self.text:
            out.append(self.text)
        return out

    @property
    def all_text(self) -> str:
        return "\n".join(self.texts)

    @property
    def tool_uses(self) -> list[tuple[str, dict[str, Any]]]:
        uses = []
        for event in self.events:
            if event.get("type") != "assistant":
                continue
            for item in (event.get("message") or {}).get("content") or []:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    uses.append((item.get("name", ""), item.get("input") or {}))
        return uses

    @property
    def permission_denials(self) -> list[dict[str, Any]]:
        return list((self.result or {}).get("permission_denials") or [])

    def problem(self) -> str | None:
        """Why this session cannot be judged on its outcome, or None."""
        if self.aborted:
            return self.aborted
        if self.error:
            return f"the harness failed while collecting the session: {self.error}"
        if self.timed_out:
            return "the claude call timed out"
        result = self.result
        if result is None:
            return f"claude produced no result event (exit code {self.returncode})"
        if result.get("is_error") or result.get("subtype") != "success":
            return f"the session ended with {result.get('subtype')!r} (is_error={result.get('is_error')})"
        return None


def parse_stream(text: str) -> list[dict[str, Any]]:
    """Parse stream-json output: one JSON object per line; other lines are skipped."""
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def missing_command_reason(init: dict[str, Any], command: str, ws: Workspace) -> str | None:
    """None if the session loaded this project's `/command`; otherwise the failure text.

    Both must hold: <work>/.claude/commands/<name>.md exists (so a same-named
    skill or built-in cannot stand in for it) and Claude Code lists the name."""
    name = command.lstrip("/")
    installed = (ws.claude_dir / "commands" / f"{name}.md").is_file()
    if installed and name in (init.get("slash_commands") or []):
        return None
    lines = [
        f"command not found: /{name} is not a command in this session "
        f"(claude-workflow/commands/{name}.md does not exist yet or was not installed).",
        f"Installed in {ws.claude_dir / 'commands'}: {ws.installed_commands() or 'none'}",
    ]
    if installed:
        lines.append(f"{name}.md is installed but Claude Code did not list /{name}.")
    if ws.install_error:
        lines.append(f"install.sh: {ws.install_error}")
    return "\n".join(lines)


def _kill(proc: subprocess.Popen) -> None:
    """Stop the whole process group, whether or not the leader has exited."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGTERM)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=10)
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=10)


def run_claude(
    ws: Workspace,
    prompt: str,
    config: HarnessConfig,
    *,
    profile: str = "default",
    resume: str | None = None,
    vault_env: bool = True,
    require_command: str | None = None,
) -> SessionResult:
    """Launch one claude -p call and collect its stream.

    With `require_command`, the session is stopped as soon as its init event
    shows that the command was not loaded, so a missing command costs no model
    turn and fails with that reason.
    """
    env = build_env(ws, vault_env=vault_env)
    check_isolation(ws.root, ws.cwd, [ws.vault], env)
    settings = ws.settings_path(profile)
    settings.write_text(json.dumps(permission_settings(ws, profile), indent=2))
    argv = build_argv(ws, prompt, config, profile=profile, resume=resume)
    session = SessionResult(argv=argv, prompt=prompt, profile=profile)

    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as err:
        proc = subprocess.Popen(
            argv, cwd=ws.cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=err, text=True, encoding="utf-8", errors="replace", start_new_session=True,
        )
        timer_fired = threading.Event()

        def on_timeout() -> None:
            timer_fired.set()
            _kill(proc)

        timer = threading.Timer(config.timeout, on_timeout)
        timer.start()
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                for event in parse_stream(line):
                    session.events.append(event)
                    if require_command and event.get("type") == "system" and event.get("subtype") == "init":
                        session.aborted = missing_command_reason(event, require_command, ws)
                if session.aborted:
                    _kill(proc)
                    break
                # Stop reading at the result event: a process the session left
                # behind can hold stdout open. claude itself is then left to exit
                # normally (it may still be saving the session for --resume), and
                # the finally clause kills whatever remains of its group.
                if session.result is not None:
                    break
            proc.wait(timeout=30)
        except Exception as exc:  # noqa: BLE001 - reported through describe(), never swallowed
            session.error = f"{type(exc).__name__}: {exc}"
        finally:
            timer.cancel()
            _kill(proc)
            if proc.stdout:
                proc.stdout.close()
        session.returncode = proc.returncode
        session.timed_out = timer_fired.is_set()
        err.seek(0)
        session.stderr = err.read()
    cost = (session.result or {}).get("total_cost_usd")
    if isinstance(cost, int | float):
        RUN_COSTS.append(float(cost))
    return session


RUN_COSTS: list[float] = []  # total_cost_usd of every collected session in this pytest run


def cost_summary() -> str:
    return f"claude sessions: {len(RUN_COSTS)}, total cost USD {sum(RUN_COSTS):.4f}"


def pytest_terminal_summary(terminalreporter) -> None:
    if RUN_COSTS:
        terminalreporter.write_line(cost_summary())


def describe(session: SessionResult) -> str:
    """Everything needed to diagnose a run without re-running it."""
    result = session.result or {}
    lines = [
        f"prompt: {session.prompt!r}",
        f"session id: {session.session_id}",
        f"exit code: {session.returncode}; timed out: {session.timed_out}",
    ]
    if session.error:
        lines.append(f"harness error: {session.error}")
    if result:
        lines.append(
            f"result: subtype={result.get('subtype')} is_error={result.get('is_error')} "
            f"turns={result.get('num_turns')} cost_usd={result.get('total_cost_usd')}"
        )
    lines.append("session text:")
    lines.append(session.all_text or "(none)")
    if session.permission_denials:
        lines.append("permission denials (Bash commands are allowed only as exact commands, so an added "
                      "redirection, `; echo $?` or a different path is denied):")
        for d in session.permission_denials:
            tool_input = d.get("tool_input") or {}
            shown = tool_input.get("command") if d.get("tool_name") == "Bash" else json.dumps(tool_input)
            lines.append(f"  {d.get('tool_name')}: {shown}")
    if session.tool_uses:
        lines.append("tool calls:")
        lines += [f"  {name}: {json.dumps(args)[:200]}" for name, args in session.tool_uses]
    if session.stderr.strip():
        lines.append("stderr (last 2000 chars):")
        lines.append(session.stderr.strip()[-2000:])
    return "\n".join(lines)


ABS_PATH_RE = re.compile(r"(?<![\w.~])/[^\s\"'`;|&<>()]+")


def paths_outside(text: str, root: Path) -> list[str]:
    """Absolute paths in `text` that are not under `root`."""
    root_r = Path(root).resolve()
    return [p for p in ABS_PATH_RE.findall(text) if not contains(root_r, Path(p))]


def allowed_bash_commands(ws: Workspace, profile: str) -> set[str]:
    """The exact commands (no wildcard) a profile allows."""
    rules = permission_settings(ws, profile)["permissions"]["allow"]
    return {r[len("Bash("):-1] for r in rules if r.startswith("Bash(") and "*" not in r}


def denials_outside_root(session: SessionResult, ws: Workspace, profile: str) -> list[dict[str, Any]]:
    """Refused calls that named a path outside the temporary root. A denial of a
    command that is exactly one the profile allows (for example the skill's own
    `[ ... -ef "/mnt/d/Second Brain" ]` check) is not counted: it names the real
    vault only to compare against it."""
    exempt = allowed_bash_commands(ws, profile)
    found = []
    for d in session.permission_denials:
        tool_input = d.get("tool_input") or {}
        command = tool_input.get("command") if d.get("tool_name") == "Bash" else json.dumps(tool_input)
        if command in exempt:
            continue
        paths = paths_outside(command or "", ws.root)
        if paths:
            found.append({"tool": d.get("tool_name"), "command": command, "paths": paths})
    return found


# --- Snapshots ---------------------------------------------------------------------------------

Snapshot = dict[str, bytes | None]  # vault-relative path -> bytes; directories end in "/" -> None


def snapshot(root: Path) -> Snapshot:
    """Every file and directory under `root` except the top-level `.git/`, with
    file bytes. A nested `.git` (a repository a session created) is included."""
    root = Path(root)
    out: Snapshot = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not (Path(dirpath) == root and d == ".git"))
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        if rel_dir != ".":
            out[rel_dir + "/"] = None
        for name in sorted(filenames):
            path = Path(dirpath) / name
            out[path.relative_to(root).as_posix()] = path.read_bytes()
    return out


@dataclass(frozen=True)
class SnapshotDiff:
    added: frozenset[str]
    removed: frozenset[str]
    changed: frozenset[str]

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.changed)

    def __str__(self) -> str:
        return "; ".join(
            f"{label}: {sorted(paths) or 'none'}"
            for label, paths in (("added", self.added), ("removed", self.removed), ("changed", self.changed))
        )


def diff_snapshots(before: Snapshot, after: Snapshot) -> SnapshotDiff:
    return SnapshotDiff(
        added=frozenset(after.keys() - before.keys()),
        removed=frozenset(before.keys() - after.keys()),
        changed=frozenset(p for p in before.keys() & after.keys() if before[p] != after[p]),
    )


Expectation = str | re.Pattern[str]


def _matches(expectation: Expectation, path: str) -> bool:
    if isinstance(expectation, re.Pattern):
        return expectation.fullmatch(path) is not None
    return expectation == path


def match_changes(
    diff: SnapshotDiff,
    *,
    added: tuple[Expectation, ...] = (),
    changed: tuple[Expectation, ...] = (),
    removed: tuple[Expectation, ...] = (),
    optional_changed: tuple[str, ...] = (),
) -> dict[Expectation, str]:
    """Check that the diff is exactly what is expected and return which path met
    each expectation. Each expectation (an exact path or a full-match regex) must
    match exactly one path, and each path may satisfy only one expectation.
    `optional_changed` lists exact paths that may change or not."""
    for opt in optional_changed:
        if not isinstance(opt, str):
            raise TypeError(f"optional_changed takes exact paths, not {opt!r}")
    found: dict[Expectation, str] = {}
    problems = []
    for label, actual, expected, optional in (
        ("added", diff.added, added, ()),
        ("removed", diff.removed, removed, ()),
        ("changed", diff.changed, changed, optional_changed),
    ):
        claimed: dict[str, Expectation] = {}
        for exp in (*expected, *optional):
            hits = sorted(p for p in actual if _matches(exp, p))
            if len(hits) > 1:
                problems.append(f"{label}: {exp!r} matched several paths: {hits}")
            elif not hits:
                if exp in expected:
                    problems.append(f"{label}: expected {exp!r}, not found")
            elif hits[0] in claimed:
                problems.append(f"{label}: {hits[0]!r} meets both {claimed[hits[0]]!r} and {exp!r}")
            else:
                claimed[hits[0]] = exp
                found[exp] = hits[0]
        unclaimed = sorted(set(actual) - claimed.keys())
        if unclaimed:
            problems.append(f"{label}: unexpected {unclaimed}")
    if problems:
        raise AssertionError("vault changes differ from the expectation:\n  " + "\n  ".join(problems) + f"\nactual: {diff}")
    return found


# --- Backend vault code (parser and checker), imported by path ----------------------------------


def _vault_package():
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from vault import conformance, parser

    return conformance, parser


def findings(vault: Path) -> set[tuple[str, str]]:
    """The checker's (code, path) pairs for a vault, as `python -m vault.conformance` prints them."""
    conformance, _ = _vault_package()
    return {(f.code, f.path) for f in conformance.check_vault(Path(vault))}


def new_findings(baseline: set[tuple[str, str]], after: set[tuple[str, str]]) -> set[tuple[str, str]]:
    return after - baseline


def parse_note(vault: Path, rel: str):
    _, parser = _vault_package()
    return parser.parse_note(rel, (Path(vault) / rel).read_bytes())


def split_body(text: str) -> str:
    """The body after the frontmatter, with web-app/backend/vault's splitter."""
    _, parser = _vault_package()
    _, body, _ = parser.split_frontmatter(text)
    return body


def note_paths(vault: Path) -> list[str]:
    """Non-ignored `.md` notes, by the checker's own ignore rules."""
    conformance, _ = _vault_package()
    return list(conformance.note_paths(Path(vault)))


def emitted_link(vault: Path, rel: str) -> str:
    """The link a command must write to `rel` (2.5): bare when the stem is unique
    among non-ignored notes, case-insensitively; folder-qualified otherwise."""
    stem = Path(rel).stem
    same = [p for p in note_paths(vault) if Path(p).stem.casefold() == stem.casefold()]
    return f"[[{stem}]]" if len(same) == 1 else f"[[{rel.removesuffix('.md')}]]"


HEADING_RE = re.compile(r"^(#{1,6}) +(.*?)[ #]*$")


def headings(text: str) -> list[str]:
    """ATX headings of a body, as `## Text`, in order (fenced code ignored)."""
    out, fence = [], None
    for line in text.splitlines():
        stripped = line.lstrip()
        if fence is None and stripped[:3] in ("```", "~~~"):
            fence = stripped[:3]
            continue
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        m = HEADING_RE.match(line)
        if m:
            out.append(f"{m.group(1)} {m.group(2).strip()}")
    return out


def section_items(text: str, level: int = 2) -> dict[str, list[str]]:
    """Non-blank lines under each heading of `level`, right-trimmed, in order.
    Indentation is kept: the fixture's expected items include it."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in split_body(text).splitlines():
        m = HEADING_RE.match(line)
        if m and len(m.group(1)) <= level:
            current = m.group(2).strip() if len(m.group(1)) == level else None
            if current is not None:
                sections.setdefault(current, [])
            continue
        if current is not None and line.strip():
            sections[current].append(line.rstrip())
    return sections


PLACEHOLDER_RE = re.compile(r"\{\{[^{}]*\}\}")


def template_frontmatter(vault: Path, name: str) -> dict[str, Any]:
    """The vault template's frontmatter, keys in order, with each `{{...}}`
    placeholder read as the text PLACEHOLDER (they are not YAML)."""
    raw = (Path(vault) / "08-System" / "Templates" / f"{name}.md").read_text(encoding="utf-8")
    _, parser = _vault_package()
    note = parser.parse_note(f"{name}.md", PLACEHOLDER_RE.sub("PLACEHOLDER", raw).encode("utf-8"))
    if note.parse_error:
        raise AssertionError(f"template {name}.md does not parse: {note.parse_error}")
    return note.frontmatter


def template_shape(vault: Path, name: str) -> tuple[list[str], list[str]]:
    """Frontmatter key order and headings of the vault's `08-System/Templates/<name>.md`."""
    text = (Path(vault) / "08-System" / "Templates" / f"{name}.md").read_text(encoding="utf-8")
    return list(template_frontmatter(vault, name)), headings(split_body(text))


def heading_order_in_text(text: str, names: tuple[str, ...]) -> list[str]:
    """Which of `names` appear as heading-like lines of `text` (alone on a line,
    optionally as a Markdown heading or bold, optionally with a colon), in order."""
    found = []
    for line in text.splitlines():
        core = line.strip().lstrip("#").strip().strip("*_").strip().rstrip(":").strip().strip("*_").strip()
        if core in names:
            found.append(core)
    return found


# --- The fixture a live scenario uses ------------------------------------------------------------


def expect(condition: bool, message: str, session: SessionResult | None = None) -> None:
    """Fail with the session's diagnostics attached."""
    if not condition:
        context = f"\n\n{describe(session)}" if session else ""
        pytest.fail(f"{message}{context}", pytrace=False)


def changes(before: Snapshot, after: Snapshot, session: SessionResult | None = None, **expected: Any) -> dict:
    """match_changes with the session's diagnostics attached on failure."""
    try:
        return match_changes(diff_snapshots(before, after), **expected)
    except AssertionError as exc:
        expect(False, str(exc), session)
        raise  # unreachable: expect() fails


class Harness:
    """One scenario's workspace plus the calls a test makes against it.

    `profile` picks the permission set; `allow_git_writes` lets a session move
    HEAD or the index (only the /eod scenarios set both)."""

    REAL_VAULT = REAL_VAULT
    TODAY = TODAY
    DAILY_NOTE = DAILY_NOTE
    STANDUP_HEADINGS = STANDUP_HEADINGS
    CARRY_FORWARD = CARRY_FORWARD
    ID_RE = ID_RE

    def __init__(self, ws: Workspace, config: HarnessConfig, profile: str = "default"):
        self.ws = ws
        self.config = config
        self.profile = profile
        self.allow_git_writes = False

    @property
    def vault(self) -> Path:
        return self.ws.vault

    def path(self, rel: str) -> Path:
        return self.ws.vault / rel

    def read(self, rel: str) -> bytes:
        return self.path(rel).read_bytes()

    def snapshot(self) -> Snapshot:
        return snapshot(self.ws.vault)

    def work_snapshot(self) -> Snapshot:
        """The session's working directory (installed skill and commands included)."""
        return snapshot(self.ws.cwd)

    def sections(self, rel: str) -> dict[str, list[str]]:
        return section_items(self.read(rel).decode("utf-8"))

    @staticmethod
    def sections_of(text: str) -> dict[str, list[str]]:
        return section_items(text)

    def findings(self) -> set[tuple[str, str]]:
        return findings(self.ws.vault)

    def note(self, rel: str):
        return parse_note(self.ws.vault, rel)

    def emitted_link(self, rel: str) -> str:
        return emitted_link(self.ws.vault, rel)

    @staticmethod
    def heading_order(text: str) -> list[str]:
        return heading_order_in_text(text, STANDUP_HEADINGS)

    def git(self, *args: str) -> str:
        return git(self.ws, *args)

    def commit_all(self, message: str) -> str:
        return commit_all(self.ws, message)

    def head(self) -> str:
        return head(self.ws)

    def run(self, command: str, args: str = "", *, profile: str | None = None, vault_env: bool = True) -> SessionResult:
        """Turn 1: run `/command args`; fail unless the command loaded and the session succeeded."""
        prompt = f"{command} {args}".strip()
        marks = git_marks(self.ws)
        session = run_claude(self.ws, prompt, self.config, profile=profile or self.profile,
                             vault_env=vault_env, require_command=command)
        self._check(session, marks)
        return session

    def reply(self, previous: SessionResult, answer: str, *, profile: str | None = None) -> SessionResult:
        """Turn 2: resume the same session with the user's answer. The permissions
        are passed again, under the profile turn 1 used unless one is given."""
        expect(bool(previous.session_id), "no session id to resume", previous)
        marks = git_marks(self.ws)
        session = run_claude(self.ws, answer, self.config, profile=profile or previous.profile,
                             resume=previous.session_id)
        self._check(session, marks)
        expect(session.session_id == previous.session_id,
               f"resume started a different session ({session.session_id}, expected {previous.session_id})", session)
        return session

    def _check(self, session: SessionResult, marks: tuple[str, bytes]) -> None:
        problem = session.problem()
        if problem:
            pytest.fail(f"{problem}\n\n{describe(session)}", pytrace=False)
        try:
            after = git_marks(self.ws)  # verifies .git/config and hooks first
        except GitTamperError as exc:
            pytest.fail(f"{exc}\n\n{describe(session)}", pytrace=False)
        if not self.allow_git_writes:
            expect(after[0] == marks[0], f"HEAD moved from {marks[0]} to {after[0]}: only /eod commits (4.1)", session)
            expect(after[1] == marks[1], "the git index changed: only /eod stages (4.1)", session)

    def changes(self, before: Snapshot, session: SessionResult | None = None, **expected: Any) -> dict:
        """Compare the vault now with `before`; see match_changes."""
        return changes(before, self.snapshot(), session, **expected)

    def unchanged(self, before: Snapshot, session: SessionResult | None = None) -> None:
        changes(before, self.snapshot(), session)

    @staticmethod
    def expect(condition: bool, message: str, session: SessionResult | None = None) -> None:
        expect(condition, message, session)  # the module-level helper

    def check_new_note(self, rel: str, note_type: str, session: SessionResult, **given: Any):
        """A note just written from the vault's `note_type` template: parses, keeps
        the template's key order and headings, has a test-mode id and today's
        `created`, has the `given` values, and every other template key keeps the
        template's value (plan 4.1). `due` is compared as a parsed date."""
        note = self.note(rel)
        text = self.read(rel).decode("utf-8", errors="replace")

        def check(condition: bool, message: str) -> None:
            expect(condition, f"{rel}: {message}\n--- {rel}\n{text}--- end", session)

        template = template_frontmatter(self.ws.vault, note_type)
        keys, template_headings = template_shape(self.ws.vault, note_type)
        check(note.parse_error is None, f"frontmatter does not parse: {note.parse_error}")
        check(note.type == note_type, f"type is {note.type!r}, expected {note_type!r}")
        check(list(note.frontmatter) == keys, f"frontmatter keys {list(note.frontmatter)} differ from the template's {keys}")
        check(bool(note.note_id) and ID_RE.match(note.note_id) is not None,
              f"id {note.note_id!r} does not match {ID_RE.pattern}")
        check(note.created == TODAY_DATE, f"created is {note.created}, expected {TODAY}")
        check(headings(note.body) == template_headings,
              f"headings {headings(note.body)} differ from the template's {template_headings}")
        for key, value in given.items():
            actual = note.due if key == "due" else note.frontmatter.get(key)
            check(actual == value, f"{key} is {actual!r}, expected {value!r}")
        for key, value in template.items():
            if key in given or key in ("id", "created"):
                continue
            check(note.frontmatter.get(key) == value,
                  f"{key} is {note.frontmatter.get(key)!r}; not given, so it must keep the template's {value!r}")
        return note

    def assert_no_new_findings(self, baseline: set[tuple[str, str]], session: SessionResult | None = None) -> None:
        extra = new_findings(baseline, self.findings())
        expect(not extra, f"conformance checker reports new findings: {sorted(extra)}", session)


@pytest.fixture
def harness_config() -> HarnessConfig:
    return HarnessConfig.from_env()


@pytest.fixture
def sb(tmp_path: Path, harness_config: HarnessConfig) -> Harness:
    """A fresh workspace for one live scenario."""
    if shutil.which(harness_config.claude_bin) is None:
        pytest.fail(f"claude executable not found: {harness_config.claude_bin!r}", pytrace=False)
    return Harness(create_workspace(tmp_path), harness_config)


@pytest.fixture
def hx():
    """This module, for the harness's own unit tests."""
    return sys.modules[__name__]
