"""Rebuild invariant (plan P1-21): incremental passes and `reindex` give the same index."""

import shutil
from pathlib import Path

import pytest

from vault import indexer
from vault.indexer import Indexer
from vault.models import Link, Note

GOLDEN = Path(__file__).resolve().parents[3] / "second-brain/fixtures/golden-vault/vault"

pytestmark = pytest.mark.django_db

NOTE_FIELDS = [
    "path", "note_id", "type", "title", "status", "priority", "project", "due", "created",
    "frontmatter", "body", "content_hash", "file_mtime", "file_size", "parse_error",
    "search_vector",
]  # fmt: skip


def dump():
    notes = []
    for note in Note.objects.order_by("path"):
        row = {name: getattr(note, name) for name in NOTE_FIELDS}
        row["tags"] = sorted(note.tags.values_list("name", flat=True))
        notes.append(row)
    links = list(
        Link.objects.order_by("source__path", "target_title").values_list(
            "source__path", "target_title"
        )
    )
    from vault.models import Tag

    return notes, links, list(Tag.objects.order_by("name").values_list("name", flat=True))


def test_incremental_equals_rebuild(isolated_vault):
    vault = isolated_vault
    shutil.copytree(GOLDEN, vault, dirs_exist_ok=True)
    idx = Indexer()
    idx.sync(vault)
    names = sorted(p for p in Note.objects.values_list("path", flat=True))
    (vault / names[0]).write_text("---\nid: 77\ntags: [x, y]\n---\n[[A]] [[B]] #z\n")
    (vault / "Added.md").write_text("added [[A]] #new")
    idx.sync(vault)
    (vault / names[1]).unlink()
    (vault / "Added.md").write_text("added again [[C]]")
    idx.sync(vault)
    (vault / names[2]).rename(vault / "Renamed.md")
    idx.sync(vault)
    idx.sync(vault)
    incremental = dump()
    indexer.reindex(vault)
    assert dump() == incremental
