"""The write pipeline shared by the create, capture, status and triage endpoints (P1-28).

One write is: validated request, one transaction holding the indexer's advisory lock (2.7), the
writer call or calls, `index_single_file` for each touched file, then the serialised indexed
note. The lock is the one every indexer pass takes, so a write never interleaves with a pass or
another write. PostgreSQL advisory transaction locks are re-entrant within one session, so the
indexer's own lock inside this transaction is a no-op.

Writer errors become the API's error statuses; anything else is logged with its traceback and
answered with a generic 500. `str(exc)` of an unexpected error is never sent to the client.
"""

import logging
from collections.abc import Callable
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction
from django.db.models import prefetch_related_objects
from rest_framework import status
from rest_framework.response import Response

from api.serializers import NoteDetailSerializer, NoteSummarySerializer
from vault import queries
from vault.indexer import LOCK_KEY, Indexer
from vault.models import Note
from vault.sanitize import WriterError
from vault.writer import ConflictError, NotFoundError, PathError, VaultWriter

logger = logging.getLogger(__name__)

GENERIC_ERROR = "The write failed unexpectedly."


def lock_vault() -> None:
    """Hold the indexer's advisory lock until the surrounding transaction ends."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_KEY])


def run_write(operation: Callable[[VaultWriter], Response]) -> Response:
    """Run `operation` in a transaction under the vault lock; map what it raises to a response.

    A raised error rolls the index back (the file system is the writer's own atomic unit). An
    operation that returns a response, an error one included, commits what it indexed.
    """
    try:
        with transaction.atomic():
            lock_vault()
            return operation(VaultWriter(Path(settings.VAULT_ROOT)))
    except Exception as exc:
        return failure(exc)


def failure(exc: Exception, **extra: str) -> Response:
    """The error response for `exc`; `extra` fields are added to the body."""
    if isinstance(exc, NotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, PathError):
        code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, ConflictError):
        code = status.HTTP_409_CONFLICT
    elif isinstance(exc, WriterError) and not _is_operational(exc):
        code = status.HTTP_422_UNPROCESSABLE_ENTITY  # ValidationError, SanitizeError, TemplateError
    else:
        logger.exception("write failed unexpectedly")
        return Response({"detail": GENERIC_ERROR, **extra}, status=500)
    return Response({"detail": str(exc), **extra}, status=code)


def _is_operational(exc: Exception) -> bool:
    """A bare `WriterError` wraps an OS failure (its text names a file system error): not for
    the client. The subclasses carry messages written for the client."""
    return type(exc) is WriterError


def locate(writer: VaultWriter, rel: str) -> str:
    """The on-disk spelling of the existing note `rel`, after the writer's path confinement.

    Raises PathError for a path that escapes the vault, is ignored, is not `.md`, passes a
    symlink or is not a regular file, and NotFoundError when it does not exist. Nothing is read
    or written.
    """
    return writer.locate(rel).relative_to(writer.root).as_posix()


def index(root: Path, rel: str) -> Note:
    """Re-index one file and return its row; a file the indexer cannot store is an error."""
    note = Indexer().index_single_file(root, rel)
    if note is None:
        raise RuntimeError(f"{rel!r} was written but could not be indexed")
    prefetch_related_objects([note], "tags")
    return note


def summary_data(note: Note) -> dict:
    return NoteSummarySerializer(note).data


def detail_data(note: Note) -> dict:
    return NoteDetailSerializer(queries.attach_detail(note)).data
