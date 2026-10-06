"""Tests for the index models: plan P1-20, design section F."""

from datetime import UTC, datetime

import pytest
from django.contrib.postgres.search import SearchQuery, TrigramSimilarity
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction

from vault.models import Link, Note, Tag

pytestmark = pytest.mark.django_db


def make_note(path, title="Title", body="", **extra):
    return Note.objects.create(
        path=path,
        title=title,
        type=extra.pop("type", "note"),
        body=body,
        content_hash="0" * 64,
        file_mtime=datetime(2026, 1, 1, tzinfo=UTC),
        file_size=len(body),
        **extra,
    )


def scalar(sql, params=()):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        row = cursor.fetchone()
    return row[0] if row else None


def test_search_vector_is_a_stored_generated_column():
    generated = scalar(
        "SELECT attgenerated FROM pg_attribute "
        "WHERE attrelid = 'vault_note'::regclass AND attname = 'search_vector'"
    )
    assert generated == "s"  # 's' = STORED ('v' = VIRTUAL, PostgreSQL 18 default)
    assert (
        scalar(
            "SELECT is_generated FROM information_schema.columns "
            "WHERE table_name = 'vault_note' AND column_name = 'search_vector'"
        )
        == "ALWAYS"
    )


def test_pg_trgm_is_installed():
    assert scalar("SELECT count(*) FROM pg_extension WHERE extname = 'pg_trgm'") == 1


def test_path_is_unique():
    make_note("a.md")
    with pytest.raises(IntegrityError), transaction.atomic():
        make_note("a.md")


def test_note_id_is_indexed_nullable_and_not_unique():
    first = make_note("a.md", note_id="abc")
    second = make_note("b.md", note_id="abc")
    third = make_note("c.md")
    assert first.note_id == second.note_id == "abc"
    assert third.note_id is None
    definitions = [
        row[0] for row in _rows("SELECT indexdef FROM pg_indexes WHERE tablename = 'vault_note'")
    ]
    note_id_indexes = [d for d in definitions if "(note_id)" in d]
    assert note_id_indexes
    assert not any("UNIQUE" in d for d in note_id_indexes)


def _rows(sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall()


def test_filter_columns_and_search_have_indexes():
    definitions = " ".join(
        row[0] for row in _rows("SELECT indexdef FROM pg_indexes WHERE tablename = 'vault_note'")
    )
    for column in ("type", "status", "project", "due"):
        assert f"({column})" in definitions
    assert "USING gin (search_vector)" in definitions
    assert "gin (title gin_trgm_ops)" in definitions


def test_ticket_key_search_finds_only_the_matching_note():
    hit = make_note("02-Work/a.md", title="Plan", body="Blocked by LOADUP-123 again")
    make_note("02-Work/b.md", title="Other", body="Mentions LOADUP-124 only")
    found = Note.objects.filter(search_vector=SearchQuery("LOADUP-123", config="simple"))
    assert list(found) == [hit]


def test_folder_name_in_path_is_searchable():
    hit = make_note("02-Work/Projects/Gida.md", title="x", body="y")
    make_note("03-Notes/Gida.md", title="x", body="y")
    found = Note.objects.filter(search_vector=SearchQuery("Projects", config="simple"))
    assert list(found) == [hit]


def test_body_is_indexed_only_up_to_the_cap():
    body = "a " * 49_995 + "earlytoken"  # token at offset 99,990
    late = "a " * 50_005 + "latetoken"  # token at offset 100,010
    early = make_note("a.md", body=body)
    make_note("b.md", body=late)
    assert body.index("earlytoken") == 99_990
    assert late.index("latetoken") == 100_010
    for word, expected in (("earlytoken", [early]), ("latetoken", [])):
        query = SearchQuery(word, config="simple")
        assert list(Note.objects.filter(search_vector=query)) == expected


def test_long_promoted_values_are_stored():
    note = make_note("a.md", priority="p" * 300, status="s" * 1000)
    note.refresh_from_db()
    assert note.priority == "p" * 300
    assert note.status == "s" * 1000


def test_trigram_similar_lookup():
    hit = make_note("a.md", title="Quarterly planning review")
    make_note("b.md", title="Grocery list")
    assert list(Note.objects.filter(title__trigram_similar="quarterly planing")) == [hit]


def test_trigram_similarity_ranks_the_closest_title_first():
    best = make_note("a.md", title="Quarterly planning review")
    make_note("b.md", title="Grocery list")
    ranked = Note.objects.annotate(sim=TrigramSimilarity("title", "quarterly planing")).order_by(
        "-sim"
    )
    assert ranked[0] == best
    assert ranked[0].sim > ranked[1].sim


def test_search_vector_updates_when_the_note_changes():
    note = make_note("a.md", body="alpha")
    Note.objects.filter(pk=note.pk).update(body="bravo")
    query = SearchQuery("bravo", config="simple")
    assert Note.objects.filter(search_vector=query).count() == 1


def test_deleting_a_note_cascades_links_and_tag_joins_but_keeps_tags():
    note = make_note("a.md")
    tag = Tag.objects.create(name="loadup")
    note.tags.add(tag)
    Link.objects.create(source=note, target_title="other")
    join = Note.tags.through
    assert join.objects.count() == 1
    note.delete()
    assert Link.objects.count() == 0
    assert join.objects.count() == 0
    assert Tag.objects.filter(name="loadup").exists()


def test_link_is_unique_per_source_and_target():
    note = make_note("a.md")
    Link.objects.create(source=note, target_title="x")
    with pytest.raises(IntegrityError), transaction.atomic():
        Link.objects.create(source=note, target_title="x")


def test_str_and_ordering():
    make_note("b.md")
    make_note("a.md")
    assert [str(n) for n in Note.objects.all()] == ["a.md", "b.md"]


def test_no_pending_migrations():
    call_command("makemigrations", check=True, dry_run=True)
