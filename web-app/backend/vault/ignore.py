"""Which vault files are notes (plan section 2.9): the one shared ignore implementation.

The conformance checker, the indexer and the writer all decide "is this a note?" here.
The vault is only ever read.

`.sbignore` dialect: UTF-8 with an optional BOM; lines split at any boundary
`str.splitlines` knows; each line is trimmed; blank lines and `#` lines are skipped. A
pattern is matched against the whole vault-relative path (`/` separators), anchored at
the vault root, case-insensitively; `*`, `?` and `[seq]` are shell wildcards and `*`
also matches `/`. A pattern ending in `/` ignores everything under any directory it
matches; any other pattern is matched against file paths only. No `**`, `!` or escaping.
"""

import fnmatch
import os
import stat
from collections.abc import Iterator
from pathlib import Path

from vault import conventions

SBIGNORE = ".sbignore"


def read_sbignore(root: Path) -> list[str]:
    """The patterns of `<vault>/.sbignore` (2.9).

    A missing file, or a symlink (which could point outside the vault), means no
    patterns; any other read error is raised.
    """
    path = root / SBIGNORE
    if path.is_symlink():
        return []
    try:
        text = path.read_bytes().decode("utf-8-sig", errors="replace")
    except FileNotFoundError:
        return []
    lines = (line.strip() for line in text.splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def is_ignored(path: str, patterns: list[str]) -> bool:
    """2.9: a dot segment, the templates folder, a non-`.md` file, or an `.sbignore` match."""
    folded = path.casefold()
    segments = folded.split("/")
    if any(segment.startswith(".") for segment in segments):
        return True
    if not folded.endswith(".md"):
        return True
    if folded.startswith(conventions.TEMPLATES_FOLDER.casefold() + "/"):
        return True
    directories = ["/".join(segments[:depth]) for depth in range(1, len(segments))]
    for pattern in (p.casefold() for p in patterns):
        if pattern.endswith("/"):
            if any(fnmatch.fnmatchcase(directory, pattern[:-1]) for directory in directories):
                return True
        elif fnmatch.fnmatchcase(folded, pattern):
            return True
    return False


def _walk_error(error: OSError) -> None:
    """os.walk `onerror`: a directory that vanished is skipped, any other error stops the run."""
    if not isinstance(error, FileNotFoundError):
        raise error


def walk_notes(root: Path) -> Iterator[tuple[str, os.stat_result]]:
    """Yield `(vault-relative path with "/", lstat result)` for every non-ignored note.

    A note is a regular file; symlinks are never notes and symlinked directories are
    never entered (os.walk does not follow them). A directory that cannot be listed
    raises its OSError, except one that vanished, which is skipped.
    """
    patterns = read_sbignore(root)
    for directory, subdirs, files in os.walk(root, onerror=_walk_error):
        # Prune dot directories (.git can be huge); is_ignored holds the rule itself.
        subdirs[:] = [name for name in subdirs if not name.startswith(".")]
        for name in files:
            full = Path(directory) / name
            rel = full.relative_to(root).as_posix()
            if is_ignored(rel, patterns):
                continue
            try:
                info = full.lstat()
            except FileNotFoundError:
                continue  # vanished while listing
            if stat.S_ISREG(info.st_mode):
                yield rel, info


def iter_note_paths(root: Path) -> list[str]:
    """Vault-relative paths (with `/`) of every non-ignored note, sorted."""
    return sorted(rel for rel, _ in walk_notes(root))
