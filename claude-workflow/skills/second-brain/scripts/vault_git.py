#!/usr/bin/env python3
"""The only way a second-brain command runs git (plan section 4.2).

Usage: python3 -I vault_git.py VERB [ARGUMENT]

  env                     print vault=, today=, now= and test_mode= (section 2.12);
                          runs no git and needs no vault
  remote                  print the configured remotes, one per line
  status                  print `git status --porcelain` (capped at 256 KiB)
  stage                   `git add -A`
  staged-diff             print the staged file names, a blank line, the staged
                          diff (capped at 256 KiB)
  head-subject            print the subject of HEAD, or nothing without a commit
  commit-eod YYYY-MM-DD   stage every change, scan the staged diff for secrets,
                          then commit as "eod: YYYY-MM-DD", or amend HEAD when its
                          subject is already exactly that

Exit codes: 0 success, including "nothing to commit" (one line on stdout);
1 refusal (one line on stderr starting "refused:"); 2 usage error (nothing run).

The vault is SECOND_BRAIN_VAULT, else DEFAULT_VAULT. No verb takes a path.
Every argument and environment variable is treated as hostile: git gets an
argument list (no shell), a fixed environment with no inherited variables, no
system or global configuration, explicit --git-dir and --work-tree, and
command-line pins for every setting these verbs could use to run a program or
reach a network. The vault's own .git/config is still read, so settings that
cannot be pinned (filter, diff and merge drivers, config hooks, includes) are
refused outright, as is any symbolic link under .git.
"""

import datetime
import os
import re
import shlex
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
# status and staged-diff output goes into a model's context.
OUTPUT_LIMIT = 256 * 1024
MAX_LISTED = 10
NOT_A_SECRET = "<!-- sbw: not-a-secret -->"

VERBS = {"env": 0, "remote": 0, "status": 0, "stage": 0, "staged-diff": 0,
         "head-subject": 0, "commit-eod": 1}
USAGE = ("usage: vault_git.py env | remote | status | stage | staged-diff | head-subject"
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

# ------------------------------------------------------------ secret scan rules
# Every pattern here runs in linear time on a long line: runs are possessive,
# and repeated starts are cut off by look-behinds, so no start position rescans
# a run another start already covered.

# Words that make a key name sensitive. "pass" counts only as a whole segment
# (DB_PASS), never inside a word (bypass, passenger).
_KEY_WORDS = re.compile(r"(?i)password|passwd|passphrase|pwd|private[ _-]?key|api[ _-]?key"
                        r"|secret|token|(?<![a-z])pass(?![a-z])")
# A key: "api key" / "private key" as two words, or one run of word characters
# and hyphens; then an optional closing quote or emphasis, then ":" or "=".
KEY_HEAD = re.compile(r"(?i)(?<![\w-])(?P<key>(?:api|private) key(?![\w-])|[\w-]++)"
                      r"[\"'`*_]*+(?P<pre>\s*+)(?P<sep>[:=])(?!=)")
# A key alone on its line with nothing after the separator.
BARE_KEY = re.compile(r"(?i)\s*+(?:[-*+]\s++)?[\"'`*_]*+(?P<key>(?:api|private) key|[\w-]++)"
                      r"[\"'`*_]*+\s*+[:=]\s*+")
_KIND_ORDER = [("private key", r"private[ _-]?key"), ("api key", r"api[ _-]?key"),
               ("password", r"passphrase|password|passwd|pwd|(?<![a-z])pass(?![a-z])"),
               ("secret", r"secret"), ("token", r"token")]
# A key whose last segment is one of these names a property, not a credential.
NON_CREDENTIAL_SUFFIXES = {"at", "date", "expires", "expiry", "ttl", "count", "length",
                           "header", "name", "url", "type", "hash", "policy", "version",
                           "endpoint"}

# Token runs are possessive, so a match always consumes its whole run and the
# next search starts after it.
TOKEN_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY(?: BLOCK)?-----"), None),
    ("GitHub token", re.compile(r"(?<![A-Za-z0-9])(?:gh[pousr]_|github_pat_)"
                                r"([A-Za-z0-9_]{20,}+)"), 1),
    ("GitLab token", re.compile(r"(?<![A-Za-z0-9])glpat-([A-Za-z0-9_-]{20,}+)"), 1),
    ("sk- key", re.compile(r"(?<![A-Za-z0-9])sk-([A-Za-z0-9_-]{20,}+)"), 1),
    ("Slack token", re.compile(r"(?<![A-Za-z0-9])xox[a-z]-([A-Za-z0-9-]{10,}+)"), 1),
    ("AWS access key", re.compile(r"(?<![A-Za-z0-9])(?:AKIA|ASIA)([0-9A-Z]{16})(?![0-9A-Za-z])"), 1),
]
URL_CREDENTIALS = re.compile(r"(?i)(?<![a-z0-9+.-])[a-z][a-z0-9+.-]*+://"
                             r"(?P<user>[^\s/:@]*+):(?P<pw>[^\s/@]++)@")
AUTH_HEADER = re.compile(r"(?i)(?<![a-z])authorization[\"']?+\s*+[:=]\s*+[\"']?+"
                         r"(?:bearer|basic|token)\s++(?P<tok>[A-Za-z0-9._~+/=-]++)")
AUTH_MIN = 16

PLACEHOLDER = re.compile(r"<.*>|\$\{.*\}|\$[A-Za-z_]\w*|\{\{.*\}\}|\{%.*%\}|%\w+%|\*+|[xX]+")
PLACEHOLDER_WORDS = {"changeme", "redacted", "example", "none", "null", "true", "false",
                     "yes", "no", "done", "todo"}
DOTTED_NAME = re.compile(r"[A-Za-z_]\w*+(?:\.[A-Za-z_]\w*+)++")
# Values that are names, not secrets (plan 4.2, refinements).
PLAIN_VALUES = [
    re.compile(r"[a-z._/:-]++"),                                   # lower-case words
    re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d++)?)?"
               r"(?:Z|[+-]\d{2}:?\d{2})?)?|\d{2}:\d{2}(?::\d{2})?"),  # ISO date or time
    re.compile(r"[+-]?\d++(?:[.,]\d++)*+(?:[a-z%]{1,12}|[KMGTP]i?B)?"),  # number, unit
    re.compile(r"v?\d++(?:\.\d++)++(?:[-+][0-9A-Za-z.-]++)?"),      # version
    re.compile(r"(?:/|~/|[A-Za-z]:[\\/]).*"),                       # path
    re.compile(r"X-[A-Za-z0-9-]++|[A-Z][a-z]++(?:-[A-Z][a-z]++)++"),  # HTTP header name
    re.compile(r"[A-Z_]++"),                                        # env variable name
    # Not in the plan's wording (reported): hyphenated words with numbers or
    # numbers-with-units (min-12-chars, expires-in-24h), and ticket keys.
    re.compile(r"(?:[a-z]++|\d++[a-z]{0,5})(?:-(?:[a-z]++|\d++[a-z]{0,5}))++"),
    re.compile(r"[A-Z][A-Z0-9]++-\d++"),
]
# A comment after whitespace. The look-behind lets only the first blank of a
# run start a match.
TRAILING_COMMENT = re.compile(r"(?<!\s)\s++(?:#|//|<!--)")
MAX_SCAN_LINE = 16 * 1024
NOT_A_SECRET_HASH = "# sbw: not-a-secret"

HUNK = re.compile(r"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_C_ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34,
              "\\": 92}
_BIDI = set("؜‎‏‪‫‬‭‮⁦⁧⁨⁩")


class Refusal(Exception):
    """A refusal; the message is printed as one line on stderr, exit code 1."""


# ------------------------------------------------------------------ helpers


def _escape(text: str, keep: str = "") -> str:
    """Control (C0, DEL, C1) and bidi characters as visible escapes, except keep."""
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


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _today_and_now(test_mode: bool, pinned) -> tuple:
    """(today as YYYY-MM-DD, now as YYYYMMDDHHMMSS) from ONE clock read, so
    the two cannot straddle midnight. The date is the pinned date in test mode
    and today in Asia/Manila otherwise; the time is always the real clock in
    Asia/Manila. env and commit-eod both use this."""
    try:
        local = _utc_now().astimezone(ZoneInfo(TIME_ZONE))
    except ZoneInfoNotFoundError:
        raise Refusal(f"time zone {TIME_ZONE} is not installed") from None
    day = pinned if test_mode else local.date().isoformat()
    return day, day.replace("-", "") + local.strftime("%H%M%S")


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
    shown = shown[:shown.rfind("\n") + 1] if "\n" in shown else shown + "\n"
    return shown + (f"[truncated: the output is {len(data)} bytes;"
                    f" only the first {OUTPUT_LIMIT} are shown]\n")


def _shell(*parts: str) -> str:
    """A terminal command for the user, safely quoted and printable. A path
    with control characters is never turned into a command."""
    if any(_escape(p) != p for p in parts):
        return ("(no command: the path contains control characters; inspect it in a"
                " file manager)")
    return " ".join(shlex.quote(p) for p in parts)


def _git_cmd(vault: str, *args: str) -> str:
    return _shell("git", "-C", vault, *args)


# ------------------------------------------------------------ mounts


def _read_mountinfo() -> str:
    with open("/proc/self/mountinfo", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _unescape_mount(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), value)


def _mount_of(path: str, mountinfo: str):
    """(mount point, root, fstype, source, options) of the longest mount holding path."""
    best = None
    for line in mountinfo.splitlines():
        left, sep, right = line.partition(" - ")
        fields, rest = left.split(), right.split(" ")
        if not sep or len(fields) < 5 or len(rest) < 2:
            continue
        point = _unescape_mount(fields[4])
        if not (_at_or_under(path, point) or point == "/"):
            continue
        if best is None or len(point) >= len(best[0]):
            best = (point, _unescape_mount(fields[3]), rest[0].lower(),
                    _unescape_mount(rest[1]),
                    _unescape_mount(rest[2]) if len(rest) > 2 else "")
    return best


def _drive_key(path: str, mountinfo: str):
    """For a path on a Windows drive mount: (drive source, path inside the drive),
    case-folded, so two mount points of one drive compare equal. Else None."""
    mount = _mount_of(path, mountinfo)
    if mount is None or mount[2] not in ("9p", "drvfs"):
        return None
    point, root, _, source, options = mount
    drive = re.search(r"path=([a-z]):", options, re.I)
    letter = (drive.group(1) if drive else source[:1]).casefold()
    inside = (root.rstrip("/") + "/" + path[len(point.rstrip("/")):].lstrip("/")).rstrip("/")
    return (letter, inside.casefold())


def _on_c_drive(path: str, mountinfo: str) -> bool:
    mount = _mount_of(path, mountinfo)
    if mount is None or mount[2] not in ("9p", "drvfs"):
        return False
    _, _, _, source, options = mount
    return source.casefold().startswith("c:") or "path=c:" in options.casefold()


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
    if verb in ("commit-eod", "env") and pinned is None:
        raise Refusal(f"test mode requires SECOND_BRAIN_TODAY for {verb}")
    return pinned


def _is_real_vault(path: str, mountinfo: str) -> bool:
    mine = {_norm(path).casefold(), os.path.realpath(path).casefold()}
    real = {_norm(DEFAULT_VAULT).casefold(), os.path.realpath(DEFAULT_VAULT).casefold()}
    if mine & real:
        return True
    key = _drive_key(os.path.realpath(path), mountinfo)
    if key is not None and key == _drive_key(os.path.realpath(DEFAULT_VAULT), mountinfo):
        return True
    try:
        return os.path.samefile(path, DEFAULT_VAULT)
    except OSError:
        return False


def _lexical_checks(raw: str) -> str:
    """Refusals that need no filesystem access. Returns the normal form."""
    if not raw.startswith("/"):
        raise Refusal("the vault must be an absolute path (set SECOND_BRAIN_VAULT)")
    if ".." in raw.split("/"):
        raise Refusal("the vault path contains a '..' component")
    path = _norm(raw)
    if _at_or_under(path, OLD_VAULT):
        raise Refusal("refusing to touch the old vault")
    if _at_or_under(path, C_DRIVE_MOUNT):
        raise Refusal("refusing a vault on drive C:")
    if any(re.search(r"~\d", part) for part in path.split("/")):
        raise Refusal("refusing a vault path with a short-name component (like DOCUME~1)")
    return path


def _vault_path(test_mode: bool) -> str:
    """The vault path after every check that needs no repository and does not
    require the vault to exist: the text checks, the test-mode real-vault
    guard and the drive-C mount check. Shared by env and every other verb."""
    raw = os.environ.get("SECOND_BRAIN_VAULT")
    if raw is None:
        raw = DEFAULT_VAULT
    path = _lexical_checks(raw)
    try:
        mountinfo = _read_mountinfo()
    except OSError as exc:
        raise Refusal(f"cannot read the mount table to check the vault's drive: {exc}") from None
    if test_mode and _is_real_vault(path, mountinfo):
        raise Refusal("test mode refuses the real vault")
    if _on_c_drive(path, mountinfo):
        raise Refusal(f"refusing a vault on a mount of drive C: {_escape(path)}")
    return path


def _check_no_symlink_in_path(path: str) -> None:
    if os.path.realpath(path) != path:
        raise Refusal(f"the vault path contains a symlink: {_escape(path)}")


def _resolve_vault(test_mode: bool) -> str:
    path = _vault_path(test_mode)
    shown = _escape(path)
    try:
        st = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        raise Refusal(f"the vault does not exist: {shown}") from None
    if stat.S_ISLNK(st.st_mode):
        raise Refusal(f"the vault is a symlink: {shown}")
    if not stat.S_ISDIR(st.st_mode):
        raise Refusal(f"the vault is not a directory: {shown}")
    _check_no_symlink_in_path(path)
    return path


def env(test_mode: bool, pinned) -> str:
    """The env verb's four lines. Runs no git and needs no vault, so it works
    before the vault exists and for a command that will only refuse."""
    raw = os.environ.get("SECOND_BRAIN_VAULT")
    if raw is not None and _escape(raw) != raw:
        raise Refusal("SECOND_BRAIN_VAULT contains a control character or line break")
    try:
        path = _vault_path(test_mode)
        _check_no_symlink_in_path(path)
    except Refusal as exc:
        raise Refusal(f"SECOND_BRAIN_VAULT: {exc}") from None
    today, now = _today_and_now(test_mode, pinned)
    return (f"vault={path}\ntoday={today}\nnow={now}\n"
            f"test_mode={1 if test_mode else 0}\n")


def _walk_git_dir(gitdir: str):
    """(path, kind) of the first link under .git, or None: a symbolic link
    anywhere, or a regular file outside objects/ with more than one hard link
    (git writes COMMIT_EDITMSG and the reflogs in place). Links are never
    followed. Objects are exempt: git hard-links them itself and never
    rewrites one."""
    objects = gitdir + "/objects"
    device = os.lstat(gitdir).st_dev
    stack = [gitdir]
    while stack:
        with os.scandir(stack.pop()) as entries:
            for entry in entries:
                if entry.is_symlink():
                    return entry.path, "symbolic"
                if entry.is_dir(follow_symlinks=False):
                    # A mount inside .git is not a link, but git would write
                    # onto another filesystem through it.
                    if os.lstat(entry.path).st_dev != device:
                        return entry.path, "mount"
                    stack.append(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    if entry.stat(follow_symlinks=False).st_nlink > 1 and \
                            not entry.path.startswith(objects + "/"):
                        return entry.path, "hard"
    return None


def _check_no_links(vault: str) -> None:
    found = _walk_git_dir(vault + "/.git")
    if found is None:
        return
    link, kind = found
    if kind == "mount":
        raise Refusal(f"{_escape(link)} is on a different filesystem (a mount inside .git),"
                      " so git would write outside the vault; unmount it in a terminal:"
                      f" {_shell('umount', link)}")
    if kind == "symbolic":
        raise Refusal(f"{_escape(link)} is a symbolic link, which git would follow out of"
                      f" the vault; inspect it, then remove it in a terminal: {_shell('rm', link)}")
    raise Refusal(f"{_escape(link)} is a hard link shared with another file, which git would"
                  " write through out of the vault; break the link in a terminal (this keeps"
                  f" its content): {_shell('cp', link, link + '.copy')} &&"
                  f" {_shell('mv', link + '.copy', link)}")


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
    for rel, why in (("commondir", "would redirect git to another repository"),
                     ("objects/info/alternates", "would read another repository")):
        if os.path.lexists(f"{gitdir}/{rel}"):
            raise Refusal(f".git/{rel} {why}; inspect it, then remove it in a terminal:"
                          f" {_shell('rm', f'{gitdir}/{rel}')}")
    _check_no_links(vault)


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
            options: list = (), literal: bool = True):
        """Run git on the vault. Returns (exit code, stdout bytes).

        options are extra global options placed before the subcommand (the
        commit identity pins)."""
        self.verify()
        cmd = [self.git, "--no-pager", "--no-optional-locks"]
        if literal:
            cmd.append("--literal-pathspecs")
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
            text = _decode(result.stderr or result.stdout)
            if "index.lock" in text and "File exists" in text:
                lock = self.gitdir + "/index.lock"
                raise Refusal("the vault's index is locked by another git process; if"
                              " no git process is running, remove the stale lock in a"
                              f" terminal: {_shell('rm', lock)}")
            detail = _escape(" | ".join(text.strip().splitlines()))[:500]
            raise Refusal(f"git {args[0]} failed: {detail}")
        return result.returncode, result.stdout


def _find_git() -> str:
    git = shutil.which("git", path=SAFE_PATH)
    if git is None:
        raise Refusal(f"git is not installed in {SAFE_PATH}")
    return git


def _check_top_level(repo: Repo) -> None:
    hint = ("check core.worktree and core.bare in a terminal: "
            + _git_cmd(repo.path, "config", "--local", "--list"))
    try:
        _, out = repo.run(["rev-parse", "--show-toplevel", "--absolute-git-dir"],
                          discover=True)
    except Refusal as exc:
        raise Refusal(f"git does not see the vault as the top level of a work tree"
                      f" ({exc}); {hint}") from None
    lines = _decode(out).split("\n")
    if lines[:2] != [repo.path, repo.gitdir]:
        raise Refusal(f"git does not report the vault as the top level of its work tree;"
                      f" {hint}")


def _config_keys(repo: Repo) -> list:
    _, out = repo.run(["config", "--list", "--name-only", "-z"])
    return [_decode(k) for k in out.split(b"\0") if k]


def _check_config(repo: Repo) -> None:
    for key in _config_keys(repo):
        if DENIED_CONFIG.match(key.lower()):
            section, _, _ = key.rpartition(".")
            if key.lower().startswith(("filter.", "hook.")) and section.count(".") >= 1:
                command = _git_cmd(repo.path, "config", "--remove-section", section)
            else:
                command = _git_cmd(repo.path, "config", "--unset-all", key)
            raise Refusal(f"the vault's git configuration sets {_escape(key)}, which can"
                          f" run a program or pull in another file; remove it in a"
                          f" terminal: {command}")


def open_vault(test_mode: bool) -> Repo:
    path = _resolve_vault(test_mode)
    _check_git_dir(path)
    repo = Repo(_find_git(), path)
    _check_top_level(repo)
    _check_config(repo)
    return repo


# ------------------------------------------------------------- state checks


def _remotes(repo: Repo) -> list:
    """(name, command that removes it), for every way a remote can be configured."""
    _, out = repo.run(["remote"])
    found = [(_decode(n), _git_cmd(repo.path, "remote", "remove", _decode(n)))
             for n in out.split(b"\n") if n]
    for key in _config_keys(repo):
        lower = key.lower()
        if lower.startswith("remote.") or re.fullmatch(r"branch\..*\.(remote|pushremote)",
                                                       lower):
            found.append((key, _git_cmd(repo.path, "config", "--unset-all", key)))
    for folder in ("remotes", "branches"):  # legacy remote files
        where = f"{repo.gitdir}/{folder}"
        if os.path.isdir(where) and not os.path.islink(where):
            found += [(n, _shell("rm", f"{where}/{n}")) for n in sorted(os.listdir(where))]
    unique, seen = [], set()
    for name, command in found:
        key = name.split(".")[1] if name.lower().startswith("remote.") else name
        if key not in seen:
            seen.add(key)
            unique.append((key, command))
    return unique


def _check_state(repo: Repo) -> None:
    """Refuse a merge, rebase, cherry-pick or revert in progress, unmerged
    paths, or a detached HEAD: each needs the user, in a terminal."""
    g = repo.gitdir
    for marker, what, abort in (
        ("MERGE_HEAD", "a merge", "merge --abort"),
        ("rebase-merge", "a rebase", "rebase --abort"),
        ("rebase-apply", "a rebase", "rebase --abort"),
        ("CHERRY_PICK_HEAD", "a cherry-pick", "cherry-pick --abort"),
        ("REVERT_HEAD", "a revert", "revert --abort"),
    ):
        if os.path.lexists(f"{g}/{marker}"):
            raise Refusal(f"the vault is in the middle of {what}; finish it, or abort it"
                          f" in a terminal (aborting discards {what}'s unfinished"
                          f" changes): {_git_cmd(repo.path, *abort.split())}")
    _, unmerged = repo.run(["ls-files", "--unmerged", "-z"])
    if unmerged:
        raise Refusal("the vault has unmerged paths; resolve them and stage them, or"
                      " in a terminal (this discards the conflicted changes): "
                      + _git_cmd(repo.path, "reset", "--merge"))
    code, _ = repo.run(["symbolic-ref", "--quiet", "HEAD"], ok=(0, 1))
    if code != 0:
        left = ("; commits made while HEAD is detached would be left behind, so check"
                " them first with " + _git_cmd(repo.path, "log", "--oneline", "-5"))
        if os.path.lexists(f"{g}/BISECT_LOG"):
            raise Refusal("the vault's HEAD is detached by a bisect; end it in a terminal: "
                          + _git_cmd(repo.path, "bisect", "reset") + left)
        raise Refusal("the vault's HEAD is detached; return to the branch in a terminal: "
                      + _git_cmd(repo.path, "switch", "main") + left)


def _is_ignored(repo: Repo, rel: str) -> bool:
    # check-ignore refuses --literal-pathspecs; the "./" prefix keeps a name
    # such as ":(icase)x" from being read as pathspec magic instead.
    code, _ = repo.run(["check-ignore", "--quiet", "--no-index", "--", "./" + rel + "/"],
                       ok=(0, 1), literal=False)
    return code == 0


def _check_no_nested_repo(repo: Repo) -> None:
    """No .git (directory, file or link) below the vault root, outside paths
    the vault's .gitignore ignores (git add -A never enters those)."""
    stack = [repo.path]
    while stack:
        current = stack.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                if entry.name.casefold() == ".git":
                    if current == repo.path:
                        continue
                    rel = os.path.relpath(current, repo.path)
                    if _is_ignored(repo, rel):
                        break
                    move = _shell("mv", current, os.path.dirname(repo.path))
                    # A .gitignore line is offered only for ordinary names: "*",
                    # "[ab]", "!x" or "#x" would mean something else there.
                    ignore = ""
                    if re.fullmatch(r"[A-Za-z0-9 ._/-]+", rel):
                        ignore = f", or add the line /{rel}/ to the vault's .gitignore"
                    raise Refusal(
                        f"a nested git repository is at {_escape(rel)}; git would record"
                        " it as a pointer, not its files. Move it out of the vault in a"
                        f" terminal ({move}){ignore}")
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)


def _local_identity(repo: Repo) -> list:
    pins = []
    for key in ("user.name", "user.email"):
        code, out = repo.run(["config", "--local", "--null", "--get", key], ok=(0, 1))
        value = _decode(out).removesuffix("\0")
        command = _git_cmd(repo.path, "config", key, "<value>")
        if code != 0 or not value.strip():
            raise Refusal(f"{key} is not set in the vault's .git/config (no global"
                          f" identity is used); set it in a terminal: {command}")
        if any(c in value for c in "\n\r\0"):
            raise Refusal(f"{key} in the vault's .git/config contains a line break;"
                          f" set it again in a terminal: {command}")
        field = key.split(".")[1]
        pins += ["-c", f"{key}={value}", "-c", f"author.{field}={value}",
                 "-c", f"committer.{field}={value}"]
    return pins


# ------------------------------------------------------------- secret scan


def _strip_comment(text: str) -> str:
    match = TRAILING_COMMENT.search(text)
    return text[:match.start()] if match else text


def _clean_value(raw: str) -> str:
    value = _strip_comment(raw.strip()).strip().rstrip(",;").strip()
    for _ in range(2):
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'`":
            value = value[1:-1].strip()
    if len(value) > 4 and value.startswith("**") and value.endswith("**"):
        value = value[2:-2]
    return value


def _is_plain(value: str, code: bool = True) -> bool:
    """A value that is a name, date, number, version, path, header name or
    placeholder rather than a secret (length and spaces aside). code=False
    skips the code-expression test, for tokens and URL passwords, where a
    dotted value (a JWT) is not code."""
    if not value.strip("*"):
        return True
    if PLACEHOLDER.fullmatch(value) or value.lower() in PLACEHOLDER_WORDS:
        return True
    if code and ("(" in value or "[" in value or DOTTED_NAME.fullmatch(value)):
        return True  # a code expression
    if re.match(r"[a-z][a-z0-9+.-]{0,30}://", value, re.I):
        return True  # a URL; credentials inside one are a separate rule
    return any(pattern.fullmatch(value) for pattern in PLAIN_VALUES)


def _looks_secret(raw: str) -> bool:
    """The plan's value rule, applied to an extracted value."""
    value = _clean_value(raw)
    if len(value) < 8 or any(c.isspace() for c in value):
        return False
    return not _is_plain(value)


def _first_token(rest: str) -> str:
    """The quoted string at the start of rest, or its first token (up to a
    space or a comma)."""
    if rest[:1] in ("'", '"', "`"):
        end = rest.find(rest[0], 1)
        return rest[:end + 1] if end > 0 else rest
    match = re.match(r"[^\s,]*+", rest)
    return match.group(0)


def _value_after(text: str, head) -> str:
    """The value a key-head introduces (plan 4.2, "Reading the value")."""
    rest = text[head.end():]
    tight = head.group("sep") == "=" and not head.group("pre") and rest[:1] not in ("", " ", "\t")
    if tight or rest.lstrip()[:1] in ("'", '"', "`"):
        return _first_token(rest.lstrip())
    stripped = rest.strip()
    # Comma-separated inline YAML or JSON: "password: x, user: bob".
    if re.search(r",\s*+[\"']?+[\w-]++[\"']?+\s*+:", stripped):
        return _first_token(stripped)
    return rest


def _key_segments(key: str) -> list:
    return re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", key)


def _credential_kind(key: str):
    """The kind of credential a key names, or None."""
    if not _KEY_WORDS.search(key):
        return None
    segments = _key_segments(key)
    if segments and segments[-1].lower() in NON_CREDENTIAL_SUFFIXES:
        return None
    for kind, pattern in _KIND_ORDER:
        if re.search(pattern, key, re.I):
            return kind
    return "secret"


def _not_plain(run: str) -> bool:
    return any(c.isdigit() or c.isupper() for c in run)


def _marked(text: str) -> bool:
    return NOT_A_SECRET in text or text.rstrip().endswith(NOT_A_SECRET_HASH)


def _bare_key_kind(text: str):
    """The credential kind of a line that is only "key:", markers ignored."""
    text = text.replace(NOT_A_SECRET, "")
    if text.rstrip().endswith(NOT_A_SECRET_HASH):
        text = text.rstrip()[:-len(NOT_A_SECRET_HASH)]
    match = BARE_KEY.fullmatch(text)
    return _credential_kind(match.group("key")) if match else None


def _line_kinds(text: str) -> list:
    """Kinds matched by one line on its own (the next-line form is in scan_diff)."""
    kinds = []
    for head in KEY_HEAD.finditer(text):
        kind = _credential_kind(head.group("key"))
        if kind and _looks_secret(_value_after(text, head)):
            kinds.append(kind)
    stripped = text.strip()
    if stripped.startswith("|"):
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        for cell, value in zip(cells, cells[1:]):
            name = cell.strip("*`_\"' ")
            if re.fullmatch(r"[\w -]++", name):
                kind = _credential_kind(name)
                if kind and _looks_secret(value):
                    kinds.append(kind)
    for kind, pattern, group in TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            if group is None or _not_plain(match.group(group)):
                kinds.append(kind)
                break
    for match in URL_CREDENTIALS.finditer(text):
        pw = match.group("pw")
        if pw != match.group("user") and not _is_plain(pw, code=False):
            kinds.append("URL credentials")
            break
    for match in AUTH_HEADER.finditer(text):
        tok = match.group("tok")
        if len(tok) >= AUTH_MIN and not _is_plain(tok, code=False) and _not_plain(tok):
            kinds.append("authorization header")
            break
    unique = []
    for kind in kinds:
        if kind not in unique:
            unique.append(kind)
    return unique


def _chunk_kinds(text: str) -> list:
    """Kinds in a long line of a binary file, scanned in overlapping chunks."""
    kinds, step, overlap = [], MAX_SCAN_LINE, 512
    for start in range(0, len(text), step):
        for kind in _line_kinds(text[max(0, start - overlap):start + step]):
            if kind not in kinds:
                kinds.append(kind)
    return kinds


def scan_diff(diff: bytes, binary: frozenset = frozenset()):
    """Scan the added lines of a diff with context lines (--unified=1).

    Returns (found, marked): found is (file, line, kind) for each match, and
    marked is (file, line) for each added line carrying the user's marker."""
    found, marked, name = [], [], "?"
    old_left = new_left = 0
    new_no = 0
    prev = None  # the previous line on the new side, for the next-line form
    for raw in diff.split(b"\n"):
        line = _decode(raw)
        if old_left > 0 or new_left > 0:
            mark, text = line[:1], line[1:]
            if mark == "+":
                new_left -= 1
                if _marked(text):
                    marked.append((name, new_no))
                elif name in binary:
                    found += [(name, new_no, kind) for kind in _chunk_kinds(text)]
                elif len(raw) - 1 > MAX_SCAN_LINE:
                    found.append((name, new_no, "line too long to scan"))
                else:
                    kinds = _line_kinds(text)
                    if prev is not None and not _marked(prev) and _looks_secret(text):
                        kind = _bare_key_kind(prev)
                        if kind and kind not in kinds:
                            kinds.append(kind)
                    found += [(name, new_no, kind) for kind in kinds]
                prev, new_no = text, new_no + 1
            elif mark == "-":
                old_left -= 1
            elif mark == " ":
                old_left, new_left = old_left - 1, new_left - 1
                prev, new_no = text, new_no + 1
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
                new_no = int(match.group(2))
                new_left = int(match.group(3) or 1)
                prev = None
    return found, marked


def _name_kinds(path: str):
    """(index of the first path component that matches, kinds), or (None, [])."""
    for i, part in enumerate(path.split("/")):
        stem = os.path.splitext(part)[0] if not part.startswith(".") else part
        kinds = _line_kinds(stem)
        if kinds:
            return i, kinds
    return None, []


def _scan(repo: Repo, base: str = None):
    """Scan the added lines and added file names of the index against base
    (default HEAD). Returns (entries for a refusal, labels of marked lines)."""
    against = [base] if base else []
    _, numstat = repo.run(["diff", "--cached", *DIFF_SAFETY, "--numstat", "--no-renames",
                           "-z", *against])
    binary = frozenset(_decode(rec.split(b"\t", 2)[2]) for rec in numstat.split(b"\0")
                       if rec.startswith(b"-\t-\t"))
    _, diff = repo.run(["diff", "--cached", *DIFF_SAFETY, "--src-prefix=a/",
                        "--dst-prefix=b/", "--text", "--no-renames", "--unified=1", *against])
    found, marked = scan_diff(diff, binary)
    _, added = repo.run(["diff", "--cached", *DIFF_SAFETY, "--name-only",
                         "--diff-filter=A", "--no-renames", "-z", *against])
    hidden, entries = {}, []
    for raw in added.split(b"\0"):
        name = _decode(raw)
        index, kinds = _name_kinds(name) if name else (None, [])
        if kinds:
            folder = "/".join(name.split("/")[:index])
            label = (_escape(folder) + "/" if folder else "") + "<name withheld>"
            hidden[name] = label
            entries += [f"{label} ({kind} in the name)" for kind in kinds]
    for name, number, kind in found:
        entries.append(f"{hidden.get(name, _escape(name))}:{number} ({kind})")
    labels = [f"{hidden.get(name, _escape(name))}:{number}" for name, number in marked]
    return entries, labels


# ------------------------------------------------------------------- verbs


def _has_head(repo: Repo) -> bool:
    code, _ = repo.run(["rev-parse", "--verify", "--quiet", "HEAD^{commit}"], ok=(0, 1))
    return code == 0


def _head_subject(repo: Repo) -> str:
    if not _has_head(repo):
        return ""
    _, out = repo.run(["log", "-1", "--no-show-signature", "--no-notes", "--no-mailmap",
                       "--format=%s", "HEAD"])
    return _decode(out).removesuffix("\n")


def _index_equals(repo: Repo, base) -> bool:
    """The index holds exactly the tree of base (None: the empty tree)."""
    if base is None:
        _, out = repo.run(["ls-files", "-z"])
        return not out
    code, _ = repo.run(["diff", "--cached", "--quiet", *DIFF_SAFETY, base], ok=(0, 1))
    return code == 0


def commit_eod(repo: Repo, date: str) -> int:
    remotes = _remotes(repo)
    if remotes:
        names = ", ".join(_escape(name) for name, _ in remotes)
        raise Refusal(f"the vault has a git remote configured ({names}); notes never"
                      f" leave this machine. Remove it in a terminal: {remotes[0][1]}")
    identity = _local_identity(repo)
    _check_state(repo)
    _check_no_nested_repo(repo)
    nothing = "nothing to commit: the vault has no changes since the last commit"
    # status takes no lock and writes nothing, so a clean vault stays untouched.
    _, changes = repo.run(["status", "--porcelain", "--ignore-submodules=all"])
    if not changes:
        print(nothing)
        return 0
    repo.run(["add", "-A"])
    has_head = _has_head(repo)
    message = f"eod: {date}"
    amend = has_head and _head_subject(repo) == message
    if has_head and _index_equals(repo, "HEAD"):
        print(nothing)
        return 0
    undone, parent = False, None
    if amend:
        code, _ = repo.run(["rev-parse", "--verify", "--quiet", "HEAD^1^{commit}"],
                           ok=(0, 1))
        parent = "HEAD^1" if code == 0 else None
        # Everything changed today was undone: the day's commit is amended to
        # match the tree, the one case where an empty amend is allowed.
        undone = _index_equals(repo, parent)
    entries, marked = _scan(repo)
    if entries:
        listed = ", ".join(entries[:MAX_LISTED])
        if len(entries) > MAX_LISTED:
            listed += f", and {len(entries) - MAX_LISTED} more"
        raise Refusal(f"the secret scan matched: {listed}. Nothing was committed and the"
                      " changes stay staged. Ask the user to remove the value, or, if it"
                      " is not a secret, to mark the line themselves; then run /eod again")
    if amend:
        # The trailer covers the amended commit's whole diff against its
        # parent, so an earlier run's marked lines are kept.
        if parent is None:
            _, empty = repo.run(["hash-object", "-t", "tree", "/dev/null"])
            parent = _decode(empty).strip()
        marked = _scan(repo, base=parent)[1]
    listed = ", ".join(marked[:MAX_LISTED])
    if len(marked) > MAX_LISTED:
        listed += f", and {len(marked) - MAX_LISTED} more"
    _check_no_links(repo.path)  # again, immediately before git writes under .git
    args = ["commit", "--quiet", "--no-verify", "--no-gpg-sign", "--cleanup=verbatim",
            "-m", message]
    if marked:
        args += ["-m", f"Unscanned-lines: {listed}"]
    if amend:
        args += ["--amend", "--no-post-rewrite"]
    if undone:
        args.append("--allow-empty")
    repo.run(args, options=identity)
    if undone:
        print(f"amended: {message} (today's changes were undone, so the day's commit now"
              " matches the vault)")
    else:
        print(f"{'amended' if amend else 'committed'}: {message}")
    if marked:
        print(f"lines the user marked not-a-secret were committed unscanned: {listed}")
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
            expected = _today_and_now(test_mode, pinned)[0]
            if date != expected:
                raise Refusal(f"the date {date} is not today ({expected})")
        if verb == "env":
            sys.stdout.write(env(test_mode, pinned))
            return 0
        repo = open_vault(test_mode)
        if verb == "remote":
            out = "".join(_escape(name) + "\n" for name, _ in _remotes(repo))
        elif verb == "status":
            _, data = repo.run(["status", "--porcelain", "--ignore-submodules=all"])
            out = _cap(_escape(_decode(data), keep="\n"))
        elif verb == "stage":
            _check_no_nested_repo(repo)
            repo.run(["add", "-A"])
            out = ""
        elif verb == "staged-diff":
            _, names = repo.run(["diff", "--cached", "--name-status", *DIFF_SAFETY])
            _, body = repo.run(["diff", "--cached", *DIFF_SAFETY, "--src-prefix=a/",
                                "--dst-prefix=b/"])
            out = ""
            if names:
                out = _cap(_escape(_decode(names) + "\n" + _decode(body), keep="\n\t"))
        elif verb == "head-subject":
            subject = _head_subject(repo)
            out = _escape(subject) + "\n" if subject else ""
        else:
            return commit_eod(repo, argv[1])
        sys.stdout.write(out)
        return 0
    except Refusal as exc:
        line = f"refused: {_escape(str(exc))}"
        print(line, file=sys.stderr)
        if verb == "env":  # a session may read only stdout
            print(line)
        return 1
    except OSError as exc:
        line = f"refused: cannot read the vault: {_escape(str(exc))}"
        print(line, file=sys.stderr)
        if verb == "env":
            print(line)
        return 1


if __name__ == "__main__":
    sys.exit(main())
