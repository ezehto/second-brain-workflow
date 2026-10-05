#!/usr/bin/env python3
"""Create a new, empty second-brain vault (plan P1-04, sections 2.6 and 2.9).

Usage: init_vault.py TARGET [--dry-run]

Creates the Phase 1 folders, copies the six seed templates, writes README.md,
.gitignore, .gitattributes and .sbignore, then makes a local-only git
repository with one initial commit. Every refusal happens before anything is
written. The vault belongs on a drive other than C:, so the whole C: drive is
refused rather than trying to recognise the old vault by its spelling.
"""

import argparse
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# The seeds live in the second-brain component: templates/ and vault-readme.md.
SEED_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_NAMES = ["task", "project", "daily", "decision", "lesson", "capture"]
SEED_FILES = [f"templates/{n}.md" for n in TEMPLATE_NAMES] + ["vault-readme.md"]

# The old vault must never be written to, indexed or migrated implicitly.
OLD_VAULT = "/mnt/c/Users/User/Documents/Obsidian Vault"
# Drive C: is refused wholesale (one directory has many names there).
C_DRIVE_MOUNT = "/mnt/c"

# Leaf folders of the Phase 1 tree (design section D); parents come with them.
PHASE1_FOLDERS = [
    "00-Inbox",
    "01-Daily/2026",
    "02-Work/Projects",
    "02-Work/Tasks",
    "05-Knowledge/Decisions",
    "05-Knowledge/Lessons",
    "08-System/Templates",
]

GITIGNORE = """\
.obsidian/workspace*.json
.obsidian/cache/
.trash/
.*.sbw-tmp-*
.DS_Store
Thumbs.db
desktop.ini
"""
GITATTRIBUTES = "* -text\n"
SBIGNORE = """\
# Vault-relative globs the dashboard index skips, one per line.
# A trailing / means a directory. Dot-prefixed paths and
# 08-System/Templates/ are always skipped.
"""

GIT_LOCAL_CONFIG = [
    ("core.autocrlf", "false"),
    ("core.filemode", "false"),
    ("core.quotepath", "false"),
]
# Applied to every repository command so that nothing from the user's config,
# hooks, templates or fsmonitor can run or alter what is committed.
GIT_OVERRIDES = [
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.fsmonitor=false",
    "-c", "core.attributesFile=/dev/null",
    "-c", "core.excludesFile=/dev/null",
    "-c", "commit.gpgsign=false",
]


class InitError(Exception):
    """A refusal or failure; the message is shown to the user."""


@dataclass
class Plan:
    target: Path            # resolved target
    name: str               # global git identity
    email: str
    git: str                # path returned by shutil.which
    existed: bool           # target existed (empty directory) at check time
    ident: tuple | None     # (st_dev, st_ino) of the existing target
    seeds: dict             # seed file -> bytes, read before any write


def _show(path) -> str:
    """Printable form of a path that may hold undecodable bytes."""
    return os.fsencode(path).decode("utf-8", "replace")


def _at_or_under(path: str, root: str) -> bool:
    path, root = path.casefold().rstrip("/"), root.casefold().rstrip("/")
    return path == root or path.startswith(root + "/")


def _read_mountinfo() -> str:
    with open("/proc/self/mountinfo", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _unescape(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), value)


def _on_c_drive(resolved: str, mountinfo: str) -> bool:
    """True if the longest mount containing `resolved` is a drvfs/9p mount of C:."""
    best_len, best = -1, None
    for line in mountinfo.splitlines():
        left, sep, right = line.partition(" - ")
        fields, rest = left.split(), right.split(" ")
        if not sep or len(fields) < 5 or len(rest) < 2:
            continue
        mount = _unescape(fields[4])
        if not _at_or_under(resolved, mount) and mount != "/":
            continue
        if len(mount) >= best_len:
            best_len, best = len(mount), (rest[0], _unescape(rest[1]),
                                          _unescape(rest[2]) if len(rest) > 2 else "")
    if best is None:
        return False
    fstype, source, options = best
    if fstype.lower() not in ("9p", "drvfs"):
        return False
    return source.casefold().startswith("c:") or "path=c:" in options.casefold()


def _base_env(keep: tuple = ()) -> dict:
    """The environment without any GIT_* variable (except those named)."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_") or k in keep}


def _global_value(git: str, key: str) -> str:
    # Only the variables that say which global file to read are kept.
    env = _base_env(keep=("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM"))
    result = subprocess.run(
        [git, "config", "--global", "--get", key],
        cwd="/", env=env, capture_output=True, text=True, errors="replace",
    )
    value = result.stdout.removesuffix("\n")
    if result.returncode != 0 or not value.strip():
        raise InitError(
            f"global git {key} is not set; run: git config --global {key} <value>"
        )
    if "\n" in value or "\r" in value:
        raise InitError(f"global git {key} contains a line break; fix it and re-run")
    return value


def _run_git(git: str, target: Path, args: list) -> str:
    """The one place repository commands run: argument list, no shell, no
    GIT_* variables, no system or global config, hooks and fsmonitor off."""
    env = _base_env()
    # The ceiling stops git searching upward out of the target for a repository.
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null",
               GIT_CEILING_DIRECTORIES=str(target.parent))
    result = subprocess.run(
        [git, *GIT_OVERRIDES, *args],
        cwd=target, env=env, capture_output=True, text=True, errors="replace",
    )
    if result.returncode != 0:
        raise InitError(
            f"git {args[0]} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


def _identity(path: Path) -> tuple:
    st = os.lstat(path)
    if not stat.S_ISDIR(st.st_mode):
        raise InitError(f"target is not a real directory: {_show(path)}")
    return (st.st_dev, st.st_ino)


def _verify(path: Path, ident: tuple) -> None:
    """The target is still the real directory seen earlier (not swapped)."""
    try:
        current = _identity(path)
    except (OSError, InitError) as exc:
        raise InitError(f"target changed during the run: {exc}") from exc
    if current != ident:
        raise InitError("target changed during the run; refusing to continue")


def check(raw: str) -> Plan:
    """Run every refusal; reads only. Lexical checks come first, so a path that
    names a forbidden place is refused before any filesystem call on it."""
    if raw == "":
        raise InitError("target path is empty")
    if os.geteuid() == 0:
        raise InitError("refusing to run as root")
    absolute = os.path.abspath(raw)
    if _at_or_under(absolute, OLD_VAULT):
        raise InitError("refusing to touch the old vault")
    if _at_or_under(absolute, C_DRIVE_MOUNT):
        raise InitError("refusing a path on drive C: (the vault belongs on another drive)")
    if any(re.search(r"~\d", part) for part in absolute.split("/")):
        raise InitError("refusing a path with a short-name component (like DOCUME~1)")
    if ".." in raw.split("/"):
        raise InitError("refusing a path containing a '..' component")
    git = shutil.which("git")
    if git is None:
        raise InitError("git is not installed")
    if _at_or_under(git, "/mnt"):
        raise InitError(f"refusing a git under /mnt (Windows git?): {git}")

    target = Path(absolute)
    try:
        if target.is_symlink():
            raise InitError(f"target is a symlink: {_show(target)}")
        resolved = target.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise InitError(f"cannot resolve target: {exc}") from exc
    if _at_or_under(resolved.as_posix(), OLD_VAULT):
        raise InitError("refusing to touch the old vault")
    if _at_or_under(resolved.as_posix(), C_DRIVE_MOUNT):
        raise InitError("refusing a path on drive C:")
    try:
        mountinfo = _read_mountinfo()
    except OSError as exc:
        raise InitError(f"cannot read mount information: {exc}") from exc
    if _on_c_drive(resolved.as_posix(), mountinfo):
        raise InitError("refusing a path on a mount of drive C:")

    existed, ident = resolved.exists(), None
    if existed:
        if not resolved.is_dir():
            raise InitError(f"target exists and is not a directory: {_show(resolved)}")
        if any(resolved.iterdir()):
            raise InitError(f"target is not empty: {_show(resolved)}")
        ident = _identity(resolved)

    seeds = {}
    for name in SEED_FILES:
        if not (SEED_DIR / name).is_file():
            raise InitError(f"seed file missing: {SEED_DIR / name}")
        seeds[name] = (SEED_DIR / name).read_bytes()
    return Plan(resolved, _global_value(git, "user.name"),
                _global_value(git, "user.email"), git, existed, ident, seeds)


def _write_new(path: Path, data: bytes) -> None:
    # "xb" is O_EXCL: it refuses an existing file or a symlink as the last path
    # component only. Parent components are protected by _verify and by creating
    # every directory ourselves under a target checked to be a real directory.
    with open(path, "xb") as fh:
        fh.write(data)


def _plan_lines(plan: Plan) -> list:
    lines = [f"target: {_show(plan.target)}"]
    lines += [f"mkdir  {f}/" for f in PHASE1_FOLDERS]
    lines += [f"copy   08-System/Templates/{n}.md" for n in TEMPLATE_NAMES]
    lines += [f"write  {f}" for f in ("README.md", ".gitignore", ".gitattributes", ".sbignore")]
    lines.append("git init -b main --template=")
    lines += [f"git config --local {k} {v}" for k, v in GIT_LOCAL_CONFIG]
    lines.append("git config --local user.name / user.email (copied from global)")
    lines.append("git add -A && git commit -m 'Initialize vault' (no remote)")
    return lines


def create(plan: Plan) -> None:
    # Accepted residual risk: a swap of the target while files are being
    # written, or a swap of a parent directory, is not prevented.
    target = plan.target
    started = False
    try:
        if plan.existed:
            ident = plan.ident
            _verify(target, ident)
            if any(target.iterdir()):  # a file may have appeared since check()
                raise InitError(f"target is not empty: {_show(target)}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.mkdir(target)  # no exist_ok: a swapped-in symlink fails here
            ident = _identity(target)
        started = True
        for folder in PHASE1_FOLDERS:
            (target / folder).mkdir(parents=True, exist_ok=True)
        for tpl in TEMPLATE_NAMES:
            _write_new(target / "08-System" / "Templates" / f"{tpl}.md",
                       plan.seeds[f"templates/{tpl}.md"])
        _write_new(target / "README.md", plan.seeds["vault-readme.md"])
        _write_new(target / ".gitignore", GITIGNORE.encode())
        _write_new(target / ".gitattributes", GITATTRIBUTES.encode())
        _write_new(target / ".sbignore", SBIGNORE.encode())

        def git(args: list) -> str:
            _verify(target, ident)  # before every git call
            return _run_git(plan.git, target, args)

        git(["init", "-b", "main", "--template="])
        for key, value in [*GIT_LOCAL_CONFIG, ("user.name", plan.name),
                           ("user.email", plan.email)]:
            git(["config", "--local", key, value])
        if git(["remote"]).strip():
            raise InitError("the new repository has a remote; refusing to continue")
        git(["add", "-A"])
        git(["commit", "--no-verify", "-m", "Initialize vault"])
    except (InitError, OSError) as exc:
        if started:
            raise InitError(
                f"{exc}; partial vault left at {_show(target)}; remove it and re-run"
            ) from exc
        raise


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a new second-brain vault.")
    parser.add_argument("target", help="directory to create the vault in")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    args = parser.parse_args(argv)
    try:
        plan = check(args.target)
        if args.dry_run:
            print("\n".join(["dry run, nothing written", *_plan_lines(plan)]))
            return 0
        create(plan)
    except (InitError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"vault created at {_show(plan.target)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
