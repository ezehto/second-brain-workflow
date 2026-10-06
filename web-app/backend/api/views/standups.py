"""Today's standup. Implemented in P1-28 and P1-30."""

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import (
    AppendStandupRequestSerializer,
    ErrorSerializer,
    NoteDetailSerializer,
    StandupExistingSerializer,
    StandupMissingSerializer,
    StartStandupResponseSerializer,
)
from api.views.common import not_implemented


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
            501: ErrorSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        return not_implemented()

    @extend_schema(
        operation_id="standups_today_start",
        tags=["standups"],
        summary="Start today's standup",
        description=(
            "Runs one sync pass under the advisory lock, then creates today's note with "
            "carry-forward (`201`, `created: true`), fills it if untouched (`200`, "
            "`filled: true`) or returns it unchanged if touched (`200`, `filled: false`)."
        ),
        request=None,
        responses={
            200: StartStandupResponseSerializer,
            201: StartStandupResponseSerializer,
            501: ErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        return not_implemented()


class StandupAppendView(APIView):
    @extend_schema(
        operation_id="standups_today_append",
        tags=["standups"],
        summary="Append to a standup section",
        description=(
            "`text` is the bare line; the writer adds the list marker by the section's rule. "
            "`409` on a hash mismatch, `404` when today's note does not exist, `422` when the "
            "section heading cannot be found."
        ),
        request=AppendStandupRequestSerializer,
        responses={
            200: NoteDetailSerializer,
            400: ErrorSerializer,
            404: ErrorSerializer,
            409: ErrorSerializer,
            422: ErrorSerializer,
            501: ErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        return not_implemented()
