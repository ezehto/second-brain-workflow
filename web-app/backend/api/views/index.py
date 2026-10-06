"""Index status and refresh. Implemented in P1-27."""

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import ErrorSerializer, IndexStatusSerializer, RefreshSummarySerializer
from api.views.common import not_implemented


class IndexStatusView(APIView):
    @extend_schema(
        operation_id="index_status",
        tags=["index"],
        summary="Index status",
        responses={200: IndexStatusSerializer, 501: ErrorSerializer},
    )
    def get(self, request: Request) -> Response:
        return not_implemented()


class IndexRefreshView(APIView):
    @extend_schema(
        operation_id="index_refresh",
        tags=["index"],
        summary="Run one sync pass now",
        description="Returns the summary of the pass; read `GET /api/index/status/` for state.",
        request=None,
        responses={200: RefreshSummarySerializer, 501: ErrorSerializer},
    )
    def post(self, request: Request) -> Response:
        return not_implemented()
