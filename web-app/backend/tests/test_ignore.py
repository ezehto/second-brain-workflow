"""Tests for the shared ignore rules (plan 2.9, task P1-21 / sbw-3i5.44)."""

import pytest

from vault.ignore import is_ignored, iter_note_paths, read_sbignore


def make(root, files):
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
            path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    "path",
    [
        ".obsidian/Note.md",
        "02-Work/.hidden/Note.md",
        "02-Work/.Note.md",
        "08-System/Templates/Extra.md",
        "08-system/TEMPLATES/Extra.md",
        "02-Work/Note.txt",
        "02-Work/Note",
    ],
)
def test_default_rules_ignore(path):
    assert is_ignored(path, [])


@pytest.mark.parametrize("path", ["02-Work/Note.md", "02-Work/Note.MD", "08-System/Other/Note.md"])
def test_default_rules_keep(path):
    assert not is_ignored(path, [])


def test_pattern_dialect():
    patterns = ["Drafts/", "a?.md", "b[12].md", "c*z.md", "Folder", "Archive/*", "x/One.md"]
    assert is_ignored("Drafts/Deep/N.md", patterns)
    assert is_ignored("deep/Drafts/N.md", patterns) is False  # anchored at the root
    assert is_ignored("ab.md", patterns)
    assert is_ignored("b2.md", patterns)
    assert is_ignored("c/y/z.md", patterns)  # `*` crosses `/`
    assert not is_ignored("Folder/N.md", patterns)  # no trailing slash: files only
    assert is_ignored("Archive/Sub/N.md", patterns)
    assert is_ignored("X/ONE.MD", patterns)  # case-insensitive


def test_read_sbignore_bom_crlf_comments(tmp_path):
    (tmp_path / ".sbignore").write_bytes("﻿# c\r\n  A.md  \r\n\r\nB/\r\n".encode())
    assert read_sbignore(tmp_path) == ["A.md", "B/"]


def test_read_sbignore_missing_and_symlink(tmp_path):
    assert read_sbignore(tmp_path) == []
    outside = tmp_path / "outside"
    outside.write_text("A.md\n")
    root = tmp_path / "v"
    root.mkdir()
    (root / ".sbignore").symlink_to(outside)
    assert read_sbignore(root) == []


def test_iter_note_paths_filters_and_sorts(tmp_path):
    make(
        tmp_path,
        {
            ".sbignore": "Skip/\n",
            "B.md": "b",
            "a/A.MD": "a",
            "Skip/S.md": "s",
            ".git/G.md": "g",
            "n.txt": "n",
        },
    )
    assert iter_note_paths(tmp_path) == ["B.md", "a/A.MD"]


def test_symlinks_are_never_followed(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "Out.md").write_text("x")
    root = tmp_path / "v"
    make(root, {"Real.md": "r"})
    (root / "Link.md").symlink_to(outside / "Out.md")
    (root / "Dir").symlink_to(outside, target_is_directory=True)
    assert iter_note_paths(root) == ["Real.md"]
