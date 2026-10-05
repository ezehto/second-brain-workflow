#!/usr/bin/env python3
"""The only way a second-brain command runs git (plan section 4.2).

Usage: vault_git.py VERB [ARGUMENT]

  remote                  print the configured remotes, one per line
  status                  print `git status --porcelain`
  stage                   `git add -A`
  staged-diff             print the staged file names, a blank line, the staged diff
  head-subject            print the subject of HEAD, or nothing without a commit
  commit-eod YYYY-MM-DD   stage every change, scan the staged diff for secrets,
                          then commit as "eod: YYYY-MM-DD", or amend HEAD when its
                          subject is already exactly that

Exit codes: 0 success; 1 refusal or failure (one line on stderr), or nothing to
commit (one line on stdout); 2 usage error (nothing is run).

The vault is SECOND_BRAIN_VAULT, else DEFAULT_VAULT. No verb takes a path.
Every argument and environment variable is treated as hostile: git gets an
argument list (no shell), a fixed environment with no inherited variables, no
system or global configuration, explicit --git-dir and --work-tree, and
command-line pins for every setting these verbs could use to run a program or
reach a network. The vault's own .git/config is still read, so settings that
cannot be pinned (filter, diff and merge drivers, config hooks, includes) are
refused outright.
"""

import datetime
import os
import re
import shutil
import stat
import subprocess
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_VAULT = "/mnt/d/Second Brain"
# The old vault must never be touched; drive C: is refused wholesale.
OLD_VAULT = "/mnt/c/Users/User/Documents/Obsidian Vault"
C_DRIVE_MOUNT = "/mnt/c"
TIME_ZONE = "Asia/Manila"
# git is looked up here only, and children get this PATH, whatever the caller's is.
SAFE_PATH = "/usr/local/bin:/usr/bin:/bin"
# staged-diff output goes into a model's context.
OUTPUT_LIMIT = 256 * 1024

VERBS = {"remote": 0, "status": 0, "stage": 0, "staged-diff": 0, "head-subject": 0,
         "commit-eod": 1}
USAGE = ("usage: vault_git.py remote | status | stage | staged-diff | head-subject"
         " | commit-eod YYYY-MM-DD")

# Pinned on every call. Command-line -c beats the repository's own config.
GIT_OVERRIDES = [
    "core.hooksPath=/dev/null",        # hooks in .git/hooks or anywhere else
    "core.fsmonitor=false",            # fsmonitor hook program
    "core.pager=cat",                  # pager (also --no-pager)
    "core.editor=false",               # editor (never needed: -m is always given)
    "core.sshCommand=false",           # transport programs
    "core.askPass=false",
    "credential.helper=",              # empty value resets the helper list
    "diff.external=",                  # external diff (also --no-ext-diff)
    "gpg.program=false",               # signing and verification
    "commit.gpgSign=false",
    "log.showSignature=false",
    "protocol.allow=never",            # no transport at all
    "core.attributesFile=/dev/null",   # no global attributes or excludes
    "core.excludesFile=/dev/null",
    "gc.auto=0",                       # no auto gc / maintenance after commit
    "maintenance.auto=false",
    "color.ui=false",                  # plain output
    "diff.noprefix=false",             # a/ and b/ prefixes the scan relies on
    "diff.mnemonicPrefix=false",
    "status.submoduleSummary=false",   # do not enter nested repositories
    "submodule.recurse=false",
]
DIFF_SAFETY = ["--no-ext-diff", "--no-textconv", "--no-color"]

# Settings that name a program or another config file and cannot be pinned by
# name (they are keyed by a driver or hook name the repository chooses).
DENIED_CONFIG = re.compile(
    r"(include|includeif|hook|filter)\.|diff\..*\.(command|textconv)$|merge\..*\.driver$"
)

_KEYWORD_KINDS = {"password": "password", "token": "token", "secret": "secret"}
SECRET_KEYWORD = re.compile(
    r"(?i)(password|token|secret|api[ _-]?key)[\"'`*_]*\s*[:=]\s*[\"'`*_]*[^\s\"'`*_]"
)
_NOT_AFTER = r"(?<![A-Za-z0-9])"
SECRET_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----")),
    ("GitHub token", re.compile(_NOT_AFTER + r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("GitHub token", re.compile(_NOT_AFTER + r"github_pat_[A-Za-z0-9_]{20,}")),
    ("GitLab token", re.compile(_NOT_AFTER + r"glpat-[A-Za-z0-9_-]{20,}")),
    ("sk- key", re.compile(_NOT_AFTER + r"sk-[A-Za-z0-9_-]{20,}")),
    ("Slack token", re.compile(_NOT_AFTER + r"xox[a-z]-[A-Za-z0-9-]{10,}")),
    ("AWS access key", re.compile(_NOT_AFTER + r"AKIA[0-9A-Z]{16}(?![0-9A-Z])")),
]
HUNK = re.compile(r"@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_C_ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34,
              "\\": 92}
_BIDI = set("؜‎‏‪‫‬‭‮⁦⁧⁨⁩")


class Refusal(Exception):
    """A refusal; the message is printed as one line on stderr, exit code 1."""


# ------------------------------------------------------------------ helpers


def _escape(text: str, keep: str = "") -> str:
    """Control and bidi characters as visible escapes, except those in keep."""
    out = []
    for ch in text:
        code = ord(ch)
        if ch in keep:
            out.append(ch)
        elif code < 0x20 or 0x7F <= code <= 0x9F:
            out.append(f"\\x{code:02x}")
        elif ch in _BIDI:
            out.append(f"\\u{code:04x}")
        else:
            out.append(ch)
    return "".join(out)


def _decode(data: bytes) -> str:
    return data.decode("utf-8", "replace")


def _norm(path: str) -> str:
    """Lexical normal form: no '.', no repeated or trailing slash."""
    return re.sub("/+", "/", os.path.normpath(path))


def _at_or_under(path: str, root: str) -> bool:
    path, root = path.casefold().rstrip("/"), root.casefold().rstrip("/")
    return path == root or path.startswith(root + "/")


def _parse_date(text: str):
    if not DATE.fullmatch(text):
        return None
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def _manila_today() -> datetime.date:
    return datetime.datetime.now(ZoneInfo(TIME_ZONE)).date()


def _unquote(name: str) -> str:
    """Undo git's C-style quoting of a path."""
    if not (len(name) >= 2 and name.startswith('"') and name.endswith('"')):
        return name
    body, out, i = name[1:-1], bytearray(), 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in _C_ESCAPES:
                out.append(_C_ESCAPES[nxt])
                i += 2
                continue
            octal = body[i + 1:i + 4]
            if re.fullmatch(r"[0-3][0-7]{2}", octal):
                out.append(int(octal, 8))
                i += 4
                continue
        out += ch.encode("utf-8", "surrogateescape")
        i += 1
    return _decode(bytes(out))


def _cap(text: str) -> str:
    data = text.encode("utf-8")
    if len(data) <= OUTPUT_LIMIT:
        return text
    shown = data[:OUTPUT_LIMIT].decode("utf-8", "ignore")
    if not shown.endswith("\n"):
        shown += "\n"
    return shown + (f"[truncated: the output is {len(data)} bytes;"
                    f" only the first {OUTPUT_LIMIT} are shown]\n")


# --------------------------------------------------------------- the vault


def _check_test_mode(verb: str):
    """Section 2.12. Returns the pinned date in test mode, else None."""
    if os.environ.get("SECOND_BRAIN_TEST_MODE") != "1":
        return None
    raw = os.environ.get("SECOND_BRAIN_VAULT")
    if not raw:
        raise Refusal("test mode requires SECOND_BRAIN_VAULT to be set")
    pinned = os.environ.get("SECOND_BRAIN_TODAY")
    if pinned is not None and _parse_date(pinned) is None:
        raise Refusal("SECOND_BRAIN_TODAY is not a valid YYYY-MM-DD date")
    if verb == "commit-eod" and pinned is None:
        raise Refusal("test mode requires SECOND_BRAIN_TODAY for commit-eod")
    return pinned


def _is_real_vault(raw: str) -> bool:
    mine = {_norm(raw).casefold(), os.path.realpath(raw).casefold()}
    real = {_norm(DEFAULT_VAULT).casefold(), os.path.realpath(DEFAULT_VAULT).casefold()}
    if mine & real:
        return True
    try:
        return os.path.samefile(raw, DEFAULT_VAULT)
    except OSError:
        return False


def _lexical_checks(raw: str) -> str:
    """Refusals that need no filesystem access. Returns the normal form."""
    if not raw.startswith("/"):
        raise Refusal("the vault must be an absolute path")
    if ".." in raw.split("/"):
        raise Refusal("the vault path contains a '..' component")
    path = _norm(raw)
    if _at_or_under(path, OLD_VAULT):
        raise Refusal("refusing to touch the old vault")
    if _at_or_under(path, C_DRIVE_MOUNT):
        raise Refusal("refusing a vault on drive C:")
    return path


def _resolve_vault(test_mode: bool) -> str:
    raw = os.environ.get("SECOND_BRAIN_VAULT")
    if raw is None:
        raw = DEFAULT_VAULT
    path = _lexical_checks(raw)
    if test_mode and _is_real_vault(path):
        raise Refusal("test mode refuses the real vault")
    shown = _escape(path)
    try:
        st = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        raise Refusal(f"the vault does not exist: {shown}") from None
    if stat.S_ISLNK(st.st_mode):
        raise Refusal(f"the vault is a symlink: {shown}")
    if not stat.S_ISDIR(st.st_mode):
        raise Refusal(f"the vault is not a directory: {shown}")
    if os.path.realpath(path) != path:
        raise Refusal(f"the vault path contains a symlink: {shown}")
    return path


def _check_git_dir(vault: str) -> None:
    gitdir = vault + "/.git"
    try:
        st = os.lstat(gitdir)
    except FileNotFoundError:
        raise Refusal("the vault has no .git directory (it is not a repository root)") from None
    if stat.S_ISLNK(st.st_mode):
        raise Refusal("the vault's .git is a symlink")
    if not stat.S_ISDIR(st.st_mode):
        raise Refusal("the vault's .git is not a directory (a .git file redirects git)")
    if os.path.lexists(gitdir + "/commondir"):
        raise Refusal(".git/commondir would redirect git to another repository")
    if os.path.lexists(gitdir + "/objects/info/alternates"):
        raise Refusal(".git/objects/info/alternates would read another repository")
    for name in ("config", "objects", "refs", "HEAD", "index", "info"):
        if os.path.islink(f"{gitdir}/{name}"):
            raise Refusal(f".git/{name} is a symlink")


def _identity_of(path: str) -> tuple:
    st = os.lstat(path)
    if not stat.S_ISDIR(st.st_mode):
        raise Refusal(f"not a real directory: {_escape(path)}")
    return (st.st_dev, st.st_ino)


class Repo:
    """The vault's repository; every git call goes through run()."""

    def __init__(self, git: str, path: str):
        self.git, self.path, self.gitdir = git, path, path + "/.git"
        self.ident = (_identity_of(path), _identity_of(self.gitdir))

    def verify(self) -> None:
        """The vault and its .git are still the directories checked earlier."""
        try:
            current = (_identity_of(self.path), _identity_of(self.gitdir))
        except (OSError, Refusal):
            current = None
        if current != self.ident:
            raise Refusal("the vault changed during the run; refusing to continue")

    def run(self, args: list, ok: tuple = (0,), discover: bool = False,
            options: list = ()):
        """Run git on the vault. Returns (exit code, stdout bytes).

        options are extra global options placed before the subcommand (the
        commit identity pins)."""
        self.verify()
        cmd = [self.git, "--no-pager", "--no-optional-locks", "--literal-pathspecs"]
        for pin in GIT_OVERRIDES:
            cmd += ["-c", pin]
        cmd += options
        if not discover:
            cmd += [f"--git-dir={self.gitdir}", f"--work-tree={self.path}"]
        cmd += args
        env = {
            "PATH": SAFE_PATH,
            "HOME": "/nonexistent",
            "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_ALLOW_PROTOCOL": "",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CEILING_DIRECTORIES": os.path.dirname(self.path),
        }
        result = subprocess.run(cmd, cwd=self.path, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True)
        if result.returncode not in ok:
            lines = _decode(result.stderr or result.stdout).strip().splitlines()
            detail = _escape(" | ".join(lines))[:500]
            raise Refusal(f"git {args[0]} failed: {detail}")
        return result.returncode, result.stdout


def _find_git() -> str:
    git = shutil.which("git", path=SAFE_PATH)
    if git is None:
        raise Refusal(f"git is not installed in {SAFE_PATH}")
    return git


def _check_top_level(repo: Repo) -> None:
    try:
        _, out = repo.run(["rev-parse", "--show-toplevel", "--absolute-git-dir"],
                          discover=True)
    except Refusal as exc:
        raise Refusal(f"git does not see the vault as the top level of a work tree ({exc})")
    lines = _decode(out).split("\n")
    if lines[:2] != [repo.path, repo.gitdir]:
        raise Refusal("git does not report the vault as the top level of its work tree")


def _config_keys(repo: Repo) -> list:
    _, out = repo.run(["config", "--list", "--name-only", "-z"])
    return [_decode(k) for k in out.split(b"\0") if k]


def _check_config(repo: Repo) -> None:
    for key in _config_keys(repo):
        if DENIED_CONFIG.match(key.lower()):
            raise Refusal(f"the vault's git configuration sets {_escape(key)}, which can"
                          " run a program or pull in another file; remove it")


def open_vault(test_mode: bool) -> Repo:
    path = _resolve_vault(test_mode)
    _check_git_dir(path)
    repo = Repo(_find_git(), path)
    _check_top_level(repo)
    _check_config(repo)
    return repo


# ------------------------------------------------------------------- verbs


def _remotes(repo: Repo) -> list:
    _, out = repo.run(["remote"])
    names = [_decode(n) for n in out.split(b"\n") if n]
    for key in _config_keys(repo):
        lower = key.lower()
        if lower.startswith("remote."):
            names.append(key[len("remote."):].rpartition(".")[0] or key)
        elif re.fullmatch(r"branch\..*\.(remote|pushremote)", lower):
            names.append(key)
    for folder in ("remotes", "branches"):  # legacy remote files git remote omits
        where = f"{repo.gitdir}/{folder}"
        if os.path.isdir(where) and not os.path.islink(where):
            names += sorted(os.listdir(where))
    seen = []
    for name in names:
        if name not in seen:
            seen.append(name)
    return seen


def _has_head(repo: Repo) -> bool:
    code, _ = repo.run(["rev-parse", "--verify", "--quiet", "HEAD^{commit}"], ok=(0, 1))
    return code == 0


def _head_subject(repo: Repo) -> str:
    if not _has_head(repo):
        return ""
    _, out = repo.run(["log", "-1", "--no-show-signature", "--no-notes", "--no-mailmap",
                       "--format=%s", "HEAD"])
    return _decode(out).removesuffix("\n")


def _staged_diff(repo: Repo, *extra: str) -> bytes:
    _, out = repo.run(["diff", "--cached", *DIFF_SAFETY, "--src-prefix=a/",
                       "--dst-prefix=b/", *extra])
    return out


def _has_staged(repo: Repo, has_head: bool) -> bool:
    if not has_head:
        _, out = repo.run(["ls-files", "-z"])
        return bool(out)
    code, _ = repo.run(["diff", "--cached", "--quiet", *DIFF_SAFETY], ok=(0, 1))
    return code == 1


def scan_diff(diff: bytes) -> list:
    """(file, kind) for each secret pattern found on an added line, in order."""
    found, name = [], "?"
    old_left = new_left = 0
    for raw in diff.split(b"\n"):
        line = _decode(raw)
        if old_left > 0 or new_left > 0:
            mark, text = line[:1], line[1:]
            if mark == "+":
                new_left -= 1
                for kind in _line_kinds(text):
                    if (name, kind) not in found:
                        found.append((name, kind))
            elif mark == "-":
                old_left -= 1
            elif mark == " ":
                old_left, new_left = old_left - 1, new_left - 1
            continue
        if line.startswith("diff --git "):
            name = "?"
        elif line.startswith("+++ "):
            target = _unquote(line[4:].rstrip("\t"))
            name = target[2:] if target.startswith("b/") else target
        elif line.startswith("@@ "):
            match = HUNK.match(line)
            if match:
                old_left = int(match.group(1) or 1)
                new_left = int(match.group(2) or 1)
    return found


def _line_kinds(text: str) -> list:
    kinds = []
    for match in SECRET_KEYWORD.finditer(text):
        word = match.group(1).lower()
        kinds.append(_KEYWORD_KINDS.get(word, "api key"))
    kinds += [kind for kind, pattern in SECRET_PATTERNS if pattern.search(text)]
    return kinds


def _local_identity(repo: Repo) -> list:
    pins = []
    for key in ("user.name", "user.email"):
        code, out = repo.run(["config", "--local", "--null", "--get", key], ok=(0, 1))
        value = _decode(out).removesuffix("\0")
        if code != 0 or not value.strip():
            raise Refusal(f"{key} is not set in the vault's .git/config;"
                          " the init script writes it (no global identity is used)")
        if any(c in value for c in "\n\r\0"):
            raise Refusal(f"{key} in the vault's .git/config contains a line break")
        field = key.split(".")[1]
        pins += ["-c", f"{key}={value}", "-c", f"author.{field}={value}",
                 "-c", f"committer.{field}={value}"]
    return pins


def commit_eod(repo: Repo, date: str) -> int:
    remotes = _remotes(repo)
    if remotes:
        raise Refusal("the vault has a git remote configured ("
                      + ", ".join(_escape(r) for r in remotes) + "); notes never leave"
                      " this machine")
    identity = _local_identity(repo)
    nothing = "nothing to commit: the vault has no changes since the last commit"
    # status takes no lock and writes nothing, so a clean vault stays untouched.
    _, changes = repo.run(["status", "--porcelain", "--ignore-submodules=all"])
    if not changes:
        print(nothing)
        return 1
    repo.run(["add", "-A"])
    has_head = _has_head(repo)
    if not _has_staged(repo, has_head):
        print(nothing)
        return 1
    found = scan_diff(_staged_diff(repo, "--text", "--no-renames", "--unified=0"))
    if found:
        listed = ", ".join(f"{_escape(name)} ({kind})" for name, kind in found)
        raise Refusal(f"the secret scan matched: {listed}; nothing was committed"
                      " (the changes stay staged)")
    message = f"eod: {date}"
    amend = has_head and _head_subject(repo) == message
    args = ["commit", "--quiet", "--no-verify", "--no-gpg-sign", "--cleanup=verbatim",
            "-m", message]
    if amend:
        args += ["--amend", "--no-post-rewrite"]
    repo.run(args, options=identity)
    print(f"{'amended' if amend else 'committed'}: {message}")
    return 0


def main(argv: list | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if (not argv or argv[0] not in VERBS or len(argv) != 1 + VERBS[argv[0]]
            or any(a.startswith("-") for a in argv)):
        print(USAGE, file=sys.stderr)
        return 2
    verb = argv[0]
    try:
        if os.geteuid() == 0:
            raise Refusal("refusing to run as root")
        test_mode = os.environ.get("SECOND_BRAIN_TEST_MODE") == "1"
        pinned = _check_test_mode(verb)
        if verb == "commit-eod":
            date = argv[1]
            if _parse_date(date) is None:
                raise Refusal(f"'{_escape(date)}' is not a real date in YYYY-MM-DD form")
            if test_mode:
                expected = pinned
            else:
                try:
                    expected = _manila_today().isoformat()
                except ZoneInfoNotFoundError:
                    raise Refusal(f"time zone {TIME_ZONE} is not installed") from None
            if date != expected:
                raise Refusal(f"the date {date} is not today ({expected})")
        repo = open_vault(test_mode)
        if verb == "remote":
            out = "".join(_escape(name) + "\n" for name in _remotes(repo))
        elif verb == "status":
            _, data = repo.run(["status", "--porcelain", "--ignore-submodules=all"])
            out = _escape(_decode(data), keep="\n")
        elif verb == "stage":
            repo.run(["add", "-A"])
            out = ""
        elif verb == "staged-diff":
            _, names = repo.run(["diff", "--cached", "--name-status", *DIFF_SAFETY])
            body = _staged_diff(repo)
            out = ""
            if names:
                out = _escape(_decode(names) + "\n" + _decode(body), keep="\n\t")
            out = _cap(out)
        elif verb == "head-subject":
            subject = _head_subject(repo)
            out = _escape(subject) + "\n" if subject else ""
        else:
            return commit_eod(repo, argv[1])
        sys.stdout.write(out)
        return 0
    except Refusal as exc:
        print(f"refused: {_escape(str(exc))}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: {_escape(str(exc))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
