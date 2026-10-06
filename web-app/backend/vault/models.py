"""Index models (design section F). The database is a rebuildable index of the vault."""

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.db.models import Value
from django.db.models.functions import Left, Replace

# Bound on body text fed to the search vector (PostgreSQL rejects tsvectors over 1 MB).
SEARCH_BODY_LIMIT = 100_000


class Note(models.Model):
    """One indexed Markdown file. `path` is the vault-relative key.

    Promoted columns (`type`, `status`, `priority`, `project`, `note_id`) are unbounded text
    because the parser keeps unknown values as written (plan 2.10). The only real cap is the
    btree index entry limit (about 2704 bytes): the indexer (P1-21) stores a promoted value
    longer than 1000 characters as null and flags it in `parse_error`; the models themselves
    accept anything up to the index limit.
    """

    path = models.CharField(max_length=1024, unique=True)
    note_id = models.TextField(null=True, blank=True, db_index=True)
    type = models.TextField(db_index=True)
    title = models.CharField(max_length=512)
    status = models.TextField(null=True, blank=True, db_index=True)
    priority = models.TextField(null=True, blank=True)
    project = models.TextField(null=True, blank=True, db_index=True)
    due = models.DateField(null=True, blank=True, db_index=True)
    created = models.DateField(null=True, blank=True)
    frontmatter = models.JSONField(default=dict)
    body = models.TextField(blank=True)
    content_hash = models.CharField(max_length=64)
    file_mtime = models.DateTimeField()  # timezone-aware
    file_size = models.PositiveBigIntegerField()
    parse_error = models.TextField(null=True, blank=True)
    # `simple` configuration: no stemming, so ticket keys and paths survive intact.
    search_vector = models.GeneratedField(
        expression=SearchVector(
            "title",
            Left("body", SEARCH_BODY_LIMIT),
            # The default parser keeps "work/projects/gida" as one token; split on "/" so
            # folder names are searchable.
            Replace("path", Value("/"), Value(" ")),
            config="simple",
        ),
        output_field=SearchVectorField(),
        db_persist=True,
    )
    tags = models.ManyToManyField("Tag", related_name="notes", blank=True)

    class Meta:
        ordering = ["path"]
        indexes = [
            GinIndex(fields=["search_vector"], name="note_search_vector_gin"),
            GinIndex(fields=["title"], name="note_title_trgm", opclasses=["gin_trgm_ops"]),
        ]

    def __str__(self) -> str:
        return self.path


class Link(models.Model):
    """A wikilink from a note. `target_title` is the normalised form; no FK to the target."""

    source = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="links")
    target_title = models.TextField(db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "target_title"], name="link_source_target")
        ]

    def __str__(self) -> str:
        return f"{self.source_id} -> {self.target_title}"


class Tag(models.Model):
    name = models.TextField(unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
