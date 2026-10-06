"""Captures: quick capture and triage. Implemented in P1-28."""

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import (
    CaptureRequestSerializer,
    ErrorSerializer,
    NoteSummarySerializer,
    PartialTriageErrorSerializer,
    TriageRequestSerializer,
    TriageResponseSerializer,
)
from api.views.common import not_implemented


class CaptureView(APIView):
    @extend_schema(
        operation_id="captures_create",
        tags=["captures"],
        summary="Quick capture",
        description="Creates a `capture` note from `text`.",
        request=CaptureRequestSerializer,
        responses={201: NoteSummarySerializer, 400: ErrorSerializer, 501: ErrorSerializer},
    )
    def post(self, request: Request) -> Response:
        return not_implemented()


class TriageView(APIView):
    @extend_schema(
        operation_id="captures_triage",
        tags=["captures"],
        summary="Triage a capture",
        description=(
            "Checks `expected_hash` first, then writes the target note, then edits the capture. "
            "If the capture edit fails, the `409` or `422` body carries `created_target`; retry "
            "with `existing_target` set to that path, which skips creation, passes the path "
            "through the writer's path confinement (`400` when it fails) and checks the target "
            "exists before editing the capture. `classification` is required unless the action "
            "is `dismiss`."
        ),
        request=TriageRequestSerializer,
        responses={
            200: TriageResponseSerializer,
            400: ErrorSerializer,
            404: ErrorSerializer,
            409: PartialTriageErrorSerializer,
            422: PartialTriageErrorSerializer,
            501: ErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        return not_implemented()
