"""Projects. Implemented in P1-26."""

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import ErrorSerializer, ProjectDetailSerializer, ProjectSummarySerializer
from api.views.common import not_implemented


class ProjectListView(APIView):
    @extend_schema(
        operation_id="projects_list",
        tags=["projects"],
        summary="Projects",
        description="Project notes with slug, status and open-task count. Not paginated.",
        responses={200: ProjectSummarySerializer(many=True), 501: ErrorSerializer},
    )
    def get(self, request: Request) -> Response:
        return not_implemented()


class ProjectDetailView(APIView):
    @extend_schema(
        operation_id="projects_detail",
        tags=["projects"],
        summary="One project",
        description="The project note, its open tasks, decisions and recent notes.",
        responses={200: ProjectDetailSerializer, 404: ErrorSerializer, 501: ErrorSerializer},
    )
    def get(self, request: Request, slug: str) -> Response:
        return not_implemented()
