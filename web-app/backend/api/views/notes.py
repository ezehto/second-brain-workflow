"""Notes: list and lookup (P1-26); create and status change are stubs until P1-28."""

from drf_spectacular.utils import extend_schema
from rest_framework import status
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
from api.views.common import not_implemented, validation_detail
from vault import clock, queries
from vault.models import Note


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
        },
    )
    def get(self, request: Request) -> Response:
        query = NoteListQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return Response(validation_detail(query.errors), status=status.HTTP_400_BAD_REQUEST)
        # An absent boolean would validate as False (HTML-input rule): keep only what was sent.
        params = {k: v for k, v in query.validated_data.items() if k in request.query_params}
        notes = queries.filter_notes(Note.objects.all(), params, clock.today())
        notes = queries.order_notes(queries.with_tags(notes), params.get("ordering", "-modified"))
        page = self.paginate_queryset(notes)
        return self.get_paginated_response(NoteSummarySerializer(page, many=True).data)

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
    @staticmethod
    def _bad_request(detail: str) -> Response:
        return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

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
        },
    )
    def get(self, request: Request) -> Response:
        query = NoteLookupQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return Response(validation_detail(query.errors), status=status.HTTP_400_BAD_REQUEST)
        path, note_id = query.validated_data.get("path"), query.validated_data.get("id")
        if (path is None) == (note_id is None):
            return self._bad_request("Give exactly one of `path` and `id`.")
        notes = queries.with_tags(
            Note.objects.filter(path=path) if path else Note.objects.filter(note_id=note_id)
        )
        found = list(notes.order_by(queries.PATH_ORDER))
        if not found:
            return Response({"detail": "No such note."}, status=status.HTTP_404_NOT_FOUND)
        if len(found) > 1:
            return Response(
                {
                    "detail": f"{len(found)} notes have this id.",
                    "candidates": [note.path for note in found],
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(NoteDetailSerializer(queries.attach_detail(found[0])).data)


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
