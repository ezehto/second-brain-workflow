"""Today's standup: read, start with carry-forward, append (P1-29)."""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import (
    AppendStandupRequestSerializer,
    AppendStandupResponseSerializer,
    ErrorSerializer,
    StandupExistingSerializer,
    StandupMissingSerializer,
    StartStandupResponseSerializer,
)
from api.views import writes
from api.views.common import validation_detail
from vault import carry_forward, clock, queries
from vault.indexer import Indexer
from vault.models import Note
from vault.writer import MAX_NOTE_BYTES, NotFoundError, VaultWriter, content_hash


class StandupTodayView(APIView):
    @extend_schema(
        operation_id="standups_today_get",
        tags=["standups"],
        summary="Today's daily note",
        description=(
            "`200` with `exists: true` and `untouched` when the note exists; `404` with "
            "`exists: false` and the carry-forward preview when it does not."
        ),
        responses={
            200: StandupExistingSerializer,
            404: StandupMissingSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        today = clock.today()
        note = queries.with_tags(Note.objects.filter(path=queries.daily_note_path(today))).first()
        data = queries.standup_today(today, note)
        if data["exists"]:
            return Response(StandupExistingSerializer(data).data)
        return Response(StandupMissingSerializer(data).data, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        operation_id="standups_today_start",
        tags=["standups"],
        summary="Start today's standup",
        description=(
            "Runs one sync pass under the advisory lock, then creates today's note with "
            "carry-forward (`201`, `created: true`), fills it if untouched (`200`, "
            "`filled: true`) or returns it unchanged if touched (`200`, `filled: false`). "
            "`409` when the note changed on disk while it was being filled."
        ),
        request=None,
        responses={
            200: StartStandupResponseSerializer,
            201: StartStandupResponseSerializer,
            400: ErrorSerializer,
            409: ErrorSerializer,
            422: ErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        return writes.run_write(start_standup)


def start_standup(writer: VaultWriter) -> Response:
    """Create or fill today's note, in the caller's transaction under the vault lock."""
    Indexer().sync(writer.root)  # review S-6: a task closed on disk a moment ago is not carried
    today = clock.today()
    items = carry_forward.preview(today)
    try:
        rel = writes.locate(writer, queries.daily_note_path(today))
    except NotFoundError:
        created = writer.create_daily(today, items)  # one write: template plus carry-forward
        return _started(writer, created.path, today, created=True, filled=False)
    if (writer.root / rel).stat().st_size > MAX_NOTE_BYTES:  # too big to edit: it is the user's
        return _started(writer, rel, today, created=False, filled=False)
    current = writes.index(writer.root, rel)
    if current.parse_error is not None:  # malformed frontmatter: the note is the user's, leave it
        return _started(writer, rel, today, created=False, filled=False)
    written = (writer.root / rel).read_bytes()
    result = writer.fill_untouched(rel, items, expected_hash=content_hash(written))
    return _started(writer, result.path, today, created=False, filled=result.changed)


def _started(writer: VaultWriter, rel: str, today, *, created: bool, filled: bool) -> Response:
    note = writes.index(writer.root, rel)
    body = {
        "created": created,
        "filled": filled,
        "note": writes.detail_data(note),
        "untouched": queries.is_untouched_daily(note, today),
    }
    return Response(body, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class StandupAppendView(APIView):
    @extend_schema(
        operation_id="standups_today_append",
        tags=["standups"],
        summary="Append to a standup section",
        description=(
            "`text` is the bare line; the writer adds the list marker by the section's rule. "
            "`409` on a hash mismatch, `404` when today's note does not exist, `422` when the "
            "text is refused."
        ),
        request=AppendStandupRequestSerializer,
        responses={
            200: AppendStandupResponseSerializer,
            400: ErrorSerializer,
            404: ErrorSerializer,
            409: ErrorSerializer,
            422: ErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        form = AppendStandupRequestSerializer(data=request.data)
        if not form.is_valid():
            return Response(validation_detail(form.errors), status=status.HTTP_400_BAD_REQUEST)
        fields = form.validated_data

        def append(writer: VaultWriter) -> Response:
            rel = writes.locate(writer, queries.daily_note_path(clock.today()))
            result = writer.append_to_section(
                rel,
                f"## {fields['section']}",
                fields["text"],
                expected_hash=fields["expected_hash"],
            )
            note = writes.detail_data(writes.index(writer.root, rel))
            return Response({"note": note, "section_created": result.section_created})

        return writes.run_write(append)
