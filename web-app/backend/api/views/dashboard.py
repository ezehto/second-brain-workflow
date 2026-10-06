"""The dashboard aggregate. Implemented in P1-26."""

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import DashboardSerializer, ErrorSerializer
from api.views.common import not_implemented


class DashboardView(APIView):
    @extend_schema(
        operation_id="dashboard",
        tags=["dashboard"],
        summary="Dashboard aggregates",
        description=(
            "Today's tasks, in progress, blocked, overdue, today's standup, recent activity, "
            "active projects, the inbox count and a small index summary."
        ),
        responses={200: DashboardSerializer, 501: ErrorSerializer},
    )
    def get(self, request: Request) -> Response:
        return not_implemented()
