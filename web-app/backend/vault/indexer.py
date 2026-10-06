"""The indexer (plan sections 2.7 and 2.9, task P1-21): vault files to the index tables.

One pass walks the vault, `stat`s every note and compares `(mtime_ns, size)` with the
index. Only new and changed files are read, hashed (SHA-256 of raw bytes) and parsed;
rows of files that are gone are deleted. A stored row has `reread_next` set until a
later pass re-reads the file and finds the same digest and stat (the racy-file rule),
so a second write that left `(mtime_ns, size)` unchanged is still caught. The flag is
a column, so one-shot passes in fresh processes and the writer's hook obey it too.

Every pass runs in one transaction under a PostgreSQL advisory lock, so the poll loop,
the refresh endpoint and the writer's single-file re-index never overlap. The database
keeps `file_mtime` at microsecond resolution, so change detection compares `mtime_ns`
floored to microseconds.
"""

import hashlib
import json
import logging
import os
import stat
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from django.db import connection, transaction
from django.db.models import Count
from django.utils import timezone

from vault.ignore import is_ignored, read_sbignore, walk_notes
from vault.models import IndexPass, Link, Note, Tag
from vault.parser import ParsedNote, parse_note

logger = logging.getLogger(__name__)

LOCK_KEY = 7_201_005_021  # fixed advisory lock id shared by every indexer entry point
STEADY_BUDGET_SECONDS = 3.0
REINDEX_BUDGET_SECONDS = 30.0
PROMOTED_LIMIT = 1000  # promoted text columns longer than this are stored as null
PATH_LIMIT = 1024  # Note.path max_length
ROW_LIMIT = 2000  # tags and link targets longer than this are skipped (btree row limit)
BATCH = 500

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_MICROSECOND = timedelta(microseconds=1)
_PROMOTED = ("note_id", "status", "priority", "project")

Opener = Callable[[Path], bytes]
Stat = tuple[int, int]  # (mtime_ns floored to microseconds, size)


@dataclass
class PassSummary:
    """The one JSON line a pass logs."""

    duration_s: float = 0.0
    scanned: int = 0
    read: int = 0
    added: int = 0
    changed: int = 0
    removed: int = 0
    moved: int = 0
    over_budget: bool = False
    # Index-wide totals after the pass, not per-pass counters.
    index_parse_errors: int = 0
    index_duplicate_ids: int = 0
    index_missing_ids: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=False)


def _read_bytes(path: Path) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def _stat_key(info: os.stat_result) -> Stat:
    return info.st_mtime_ns // 1000, info.st_size


def _mtime(micros: int) -> datetime:
    return _EPOCH + timedelta(microseconds=micros)


def scan(root: Path) -> dict[str, os.stat_result]:
    """Every non-ignored note: vault-relative path to its lstat result."""
    return dict(walk_notes(root))


class Unstorable(ValueError):
    """A file that cannot be indexed at all (its path does not fit the column)."""


@contextmanager
def quiet_info() -> Iterator[None]:
    """Hold back this module's INFO lines so a one-shot command prints only its summary."""
    previous = logger.level
    logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        logger.setLevel(previous)


def _row(parsed: ParsedNote, digest: str, key: Stat) -> tuple[dict, list[str], list[str]]:
    """Note columns, tags and link targets for storage, with the length limits applied."""
    if len(parsed.path) > PATH_LIMIT:
        raise Unstorable(f"path longer than {PATH_LIMIT} characters")
    problems = [parsed.parse_error] if parsed.parse_error else []
    values = {name: getattr(parsed, name) for name in (*_PROMOTED, "type")}
    for name, value in values.items():
        if value is not None and len(value) > PROMOTED_LIMIT:
            problems.append(f"{name} longer than {PROMOTED_LIMIT} characters, not indexed")
            values[name] = "note" if name == "type" else None  # `type` is not nullable
    tags = sorted(tag for tag in parsed.tags if len(tag) <= ROW_LIMIT)
    links = sorted(target for target in parsed.links if len(target) <= ROW_LIMIT)
    if len(tags) < len(parsed.tags):
        problems.append(f"tag longer than {ROW_LIMIT} characters skipped")
    if len(links) < len(parsed.links):
        problems.append(f"link target longer than {ROW_LIMIT} characters skipped")
    columns = {
        **values,
        "path": parsed.path,
        "title": parsed.title,
        "due": parsed.due,
        "created": parsed.created,
        "frontmatter": parsed.frontmatter,
        "body": parsed.body,
        "content_hash": digest,
        "file_mtime": _mtime(key[0]),
        "file_size": key[1],
        "parse_error": "; ".join(problems) or None,
        "reread_next": True,  # the racy rule: trusted by stat only after one more read
    }
    return columns, tags, links


def _chunks(items: list, size: int = BATCH):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _store(rows: list[tuple[dict, list[str], list[str]]]) -> None:
    """Upsert notes and replace their links and tag sets."""
    if not rows:
        return
    update_fields = [name for name in rows[0][0] if name != "path"]
    for chunk in _chunks(rows):
        Note.objects.bulk_create(
            [Note(**columns) for columns, _, _ in chunk],
            update_conflicts=True,
            unique_fields=["path"],
            update_fields=update_fields,
        )
    ids = {}
    paths = [columns["path"] for columns, _, _ in rows]
    for chunk in _chunks(paths):
        ids.update(Note.objects.filter(path__in=chunk).values_list("path", "id"))
    for chunk in _chunks(list(ids.values())):
        Link.objects.filter(source_id__in=chunk).delete()
        Note.tags.through.objects.filter(note_id__in=chunk).delete()
    Link.objects.bulk_create(
        [
            Link(source_id=ids[columns["path"]], target_title=target)
            for columns, _, links in rows
            for target in links
        ],
        batch_size=BATCH,
    )
    names = sorted({tag for _, tags, _ in rows for tag in tags})
    Tag.objects.bulk_create([Tag(name=name) for name in names], ignore_conflicts=True)
    tag_ids = {}
    for chunk in _chunks(names):
        tag_ids.update(Tag.objects.filter(name__in=chunk).values_list("name", "id"))
    Note.tags.through.objects.bulk_create(
        [
            Note.tags.through(note_id=ids[columns["path"]], tag_id=tag_ids[tag])
            for columns, tags, _ in rows
            for tag in tags
        ],
        batch_size=BATCH,
    )


def _drop_unused_tags() -> None:
    Tag.objects.filter(notes__isnull=True).delete()


def _lstat_regular(root: Path, rel: str) -> os.stat_result | None:
    """lstat of a regular file reached without crossing a symlink, else None."""
    current = root
    parts = rel.split("/")
    for index, part in enumerate(parts):
        current = current / part
        try:
            info = current.lstat()
        except (FileNotFoundError, NotADirectoryError):
            return None
        if stat.S_ISLNK(info.st_mode):
            return None
        last = index == len(parts) - 1
        if last and not stat.S_ISREG(info.st_mode):
            return None
        if not last and not stat.S_ISDIR(info.st_mode):
            return None
    return info


def _lock() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_KEY])


class Indexer:
    """Runs passes against a vault root. The racy-file memory is the `Note.reread_next` column."""

    def __init__(self, opener: Opener = _read_bytes) -> None:
        self._open = opener

    def sync(self, root: Path, *, force: bool = False) -> PassSummary:
        """One pass. `force` reads every file regardless of stat."""
        with transaction.atomic():
            _lock()
            return self._pass(Path(root), force=force, budget=STEADY_BUDGET_SECONDS)

    def reindex(self, root: Path) -> PassSummary:
        """Empty the four index tables, then read every note. One transaction: all or nothing."""
        tables = [
            Note._meta.db_table,
            Link._meta.db_table,
            Tag._meta.db_table,
            Note.tags.through._meta.db_table,
        ]
        quoted = ", ".join(connection.ops.quote_name(name) for name in tables)
        with transaction.atomic():
            _lock()
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")  # settle pending FK checks
                cursor.execute(f"TRUNCATE TABLE {quoted}")  # noqa: S608 - quoted ORM table names
            return self._pass(Path(root), force=True, budget=REINDEX_BUDGET_SECONDS)

    def index_single_file(self, root: Path, rel_path: str) -> Note | None:
        """Re-index one note (the writer's hook) and return its row.

        `rel_path` must be canonical and vault-relative with `/` separators: an absolute path,
        an empty, `.` or `..` segment, a backslash or a NUL raises ValueError.
        A path that is ignored, missing, not a regular file, or reached through a symlink
        is treated as gone: its row is deleted if present and None is returned.
        Other read errors (permissions) propagate.
        """
        root = Path(root)
        if (
            any(segment in ("", ".", "..") for segment in rel_path.split("/"))
            or "\\" in rel_path
            or "\x00" in rel_path
        ):
            raise ValueError(f"not a canonical vault-relative path: {rel_path!r}")
        with transaction.atomic():
            _lock()
            info = None
            if not is_ignored(rel_path, read_sbignore(root)):
                info = _lstat_regular(root, rel_path)
            data = self._read(root, rel_path) if info is not None else None
            if data is None:
                Note.objects.filter(path=rel_path).delete()
                _drop_unused_tags()
                return None
            digest = hashlib.sha256(data).hexdigest()
            try:
                row = _row(parse_note(rel_path, data), digest, _stat_key(info))
            except Unstorable as error:
                logger.warning("indexer skipped %s: %s", rel_path[:80], error)
                return None
            _store([row])
            _drop_unused_tags()
            return Note.objects.get(path=rel_path)

    def _read(self, root: Path, rel: str) -> bytes | None:
        try:
            return self._open(root / rel)
        except FileNotFoundError:
            return None

    def _pass(self, root: Path, *, force: bool, budget: float) -> PassSummary:
        started = time.monotonic()
        summary = PassSummary()
        found = {rel: _stat_key(info) for rel, info in walk_notes(root)}
        summary.scanned = len(found)
        indexed = {
            path: ((int((mtime - _EPOCH) // _MICROSECOND), size), note_id, digest, reread)
            for path, mtime, size, note_id, digest, reread in Note.objects.values_list(
                "path", "file_mtime", "file_size", "note_id", "content_hash", "reread_next"
            )
        }
        todo = [
            rel
            for rel, key in found.items()
            if force or rel not in indexed or indexed[rel][0] != key or indexed[rel][3]
        ]
        rows, read_count, added, settled = [], 0, {}, []
        for rel in sorted(todo):
            try:
                data = self._read(root, rel)
            except OSError as error:  # unreadable: keep the old row, try again next pass
                logger.warning("indexer could not read %s: %s", rel[:80], error)
                continue
            if data is None:  # vanished since the scan: treated as removed
                found.pop(rel)
                continue
            read_count += 1
            digest = hashlib.sha256(data).hexdigest()
            known = indexed.get(rel)
            if known and known[2] == digest and known[0] == found[rel]:
                if known[3]:
                    settled.append(rel)  # same digest and stat on the re-read: trust stat now
                continue
            try:
                columns, tags, links = _row(parse_note(rel, data), digest, found[rel])
            except Unstorable as error:
                logger.warning("indexer skipped %s: %s", rel[:80], error)
                found.pop(rel)
                read_count -= 1
                continue
            rows.append((columns, tags, links))
            if known is None:
                summary.added += 1
                added[rel] = columns["note_id"]
            elif known[2] != digest:  # a bare touch refreshes the stat only
                summary.changed += 1
        gone = sorted(set(indexed) - set(found))
        _store(rows)
        for chunk in _chunks(gone):
            Note.objects.filter(path__in=chunk).delete()
        summary.read = read_count
        summary.removed = len(gone)
        self._log_moves(gone, indexed, added, summary)
        for chunk in _chunks(settled):
            Note.objects.filter(path__in=chunk).update(reread_next=False)
        _drop_unused_tags()
        self._count_index(summary)
        summary.duration_s = round(time.monotonic() - started, 3)
        summary.over_budget = summary.duration_s > budget
        if summary.over_budget:
            logger.warning(
                "indexer pass took %.3f s, over the %.0f s budget", summary.duration_s, budget
            )
        self._record(summary)
        return summary

    @staticmethod
    def _record(summary: PassSummary) -> None:
        """Persist the pass for the status endpoint (the single `IndexPass` row)."""
        IndexPass.objects.update_or_create(
            pk=IndexPass.SINGLETON_PK,
            defaults={
                "finished_at": timezone.now(),
                "duration_ms": round(summary.duration_s * 1000),
                "summary": asdict(summary),
            },
        )

    @staticmethod
    def _log_moves(gone, indexed, added, summary: PassSummary) -> None:
        """A removed path and an added path with the same non-null id: logged as moved."""
        old_by_id = {indexed[path][1]: path for path in gone if indexed[path][1] is not None}
        for new, note_id in sorted(added.items()):
            if note_id is not None and note_id in old_by_id:
                summary.moved += 1
                logger.info("moved: %s -> %s (id %s)", old_by_id[note_id], new, note_id)

    @staticmethod
    def _count_index(summary: PassSummary) -> None:
        summary.index_parse_errors = Note.objects.filter(parse_error__isnull=False).count()
        summary.index_missing_ids = Note.objects.filter(note_id__isnull=True).count()
        summary.index_duplicate_ids = (
            Note.objects.filter(note_id__isnull=False)
            .values("note_id")
            .annotate(copies=Count("id"))
            .filter(copies__gt=1)
            .count()
        )


def sync(root: Path, *, force: bool = False, indexer: Indexer | None = None) -> PassSummary:
    """One pass over the vault."""
    return (indexer or Indexer()).sync(root, force=force)


def reindex(root: Path, *, indexer: Indexer | None = None) -> PassSummary:
    return (indexer or Indexer()).reindex(root)


def index_single_file(root: Path, rel_path: str, *, indexer: Indexer | None = None) -> Note | None:
    return (indexer or Indexer()).index_single_file(root, rel_path)


def watch(
    root: Path,
    interval: float,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] | None = None,
    max_passes: int | None = None,
    stop_event: threading.Event | None = None,
    indexer: Indexer | None = None,
) -> int:
    """Run passes every `interval` seconds until stopped; returns the number of passes.

    A pass that raises is logged and the loop carries on. The sleep is the interval
    minus the pass time, never negative; the default sleep wakes on `stop_event`.
    """
    stop = stop_event or threading.Event()
    sleep = sleep or stop.wait
    indexer = indexer or Indexer()
    passes = 0
    while not stop.is_set() and (max_passes is None or passes < max_passes):
        started = clock()
        try:
            logger.info(indexer.sync(Path(root)).to_json())
        except Exception:
            logger.exception("indexer pass failed")
        passes += 1
        if stop.is_set() or (max_passes is not None and passes >= max_passes):
            break
        sleep(max(0.0, interval - (clock() - started)))
    return passes
