"""The dashboard aggregate (P1-26)."""

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import DashboardSerializer, NoteDetailSerializer
from api.views.index import compute_problems, problem_count
from vault import clock, queries
from vault.models import IndexPass


class DashboardView(APIView):
    @extend_schema(
        operation_id="dashboard",
        tags=["dashboard"],
        summary="Dashboard aggregates",
        description=(
            "Today's tasks, in progress, blocked, overdue, today's standup, recent activity, "
            "active projects, the inbox count and a small index summary."
        ),
        responses={200: DashboardSerializer},
    )
    def get(self, request: Request) -> Response:
        data = queries.dashboard(clock.today())
        standup = data["standup"]
        if standup["exists"]:
            standup["note"] = NoteDetailSerializer(standup["note"]).data
        last = IndexPass.objects.filter(pk=IndexPass.SINGLETON_PK).first()
        data["index"] = {
            "last_pass_at": last.finished_at if last else None,
            "problem_count": problem_count(compute_problems()),
        }
        return Response(DashboardSerializer(data).data)
