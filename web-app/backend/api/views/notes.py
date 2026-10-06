"""Notes: list, lookup, create and status change. Implemented in P1-26 and P1-28."""

from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import (
    AmbiguousLookupErrorSerializer,
    CreateNoteRequestSerializer,
    ErrorSerializer,
    NoteDetailSerializer,
    NoteListQuerySerializer,
    NoteLookupQuerySerializer,
    NotePagination,
    NoteSummarySerializer,
    StatusChangeRequestSerializer,
)
from api.views.common import not_implemented


class NoteListCreateView(GenericAPIView):
    pagination_class = NotePagination
    serializer_class = NoteSummarySerializer

    @extend_schema(
        operation_id="notes_list",
        tags=["notes"],
        summary="List notes",
        description=(
            "Filters combine with AND. Ordering defaults to `-modified`; every ordering ends "
            "with `path`. Paginated with `page` and `page_size` (default 50, at most 200)."
        ),
        parameters=[NoteListQuerySerializer],
        responses={
            200: NoteSummarySerializer(many=True),
            400: ErrorSerializer,
            501: ErrorSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        return not_implemented()

    @extend_schema(
        operation_id="notes_create",
        tags=["notes"],
        summary="Create a note from a template",
        request=CreateNoteRequestSerializer,
        responses={
            201: NoteSummarySerializer,
            400: ErrorSerializer,
            409: ErrorSerializer,
            422: ErrorSerializer,
            501: ErrorSerializer,
        },
        description=(
            "`409` on a same-folder name collision; `422` for an unknown project. "
            "Implemented in P1-28."
        ),
    )
    def post(self, request: Request) -> Response:
        return not_implemented()


class NoteLookupView(APIView):
    @extend_schema(
        operation_id="notes_lookup",
        tags=["notes"],
        summary="One note by path or id",
        description=(
            "Exactly one of `path` and `id`. An `id` matching several notes returns `409` with "
            "the candidate paths."
        ),
        parameters=[NoteLookupQuerySerializer],
        responses={
            200: NoteDetailSerializer,
            400: ErrorSerializer,
            404: ErrorSerializer,
            409: AmbiguousLookupErrorSerializer,
            501: ErrorSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        return not_implemented()


class NoteStatusView(APIView):
    @extend_schema(
        operation_id="notes_status",
        tags=["notes"],
        summary="Change a note's status",
        description=(
            "Validates the status against the vocabulary of the note's type. `409` on a hash "
            "mismatch, `422` on malformed frontmatter or a status outside the vocabulary. "
            "Implemented in P1-28."
        ),
        request=StatusChangeRequestSerializer,
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
