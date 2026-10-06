"""Projects (P1-26)."""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import ErrorSerializer, ProjectDetailSerializer, ProjectSummarySerializer
from vault import queries


class ProjectListView(APIView):
    @extend_schema(
        operation_id="projects_list",
        tags=["projects"],
        summary="Projects",
        description="Project notes with slug, status and open-task count. Not paginated.",
        responses={200: ProjectSummarySerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        return Response(ProjectSummarySerializer(queries.project_list(), many=True).data)


class ProjectDetailView(APIView):
    @extend_schema(
        operation_id="projects_detail",
        tags=["projects"],
        summary="One project",
        description="The project note, its open tasks, decisions and recent notes.",
        responses={200: ProjectDetailSerializer, 404: ErrorSerializer},
    )
    def get(self, request: Request, slug: str) -> Response:
        detail = queries.project_detail(slug)
        if detail is None:
            return Response({"detail": "No such project."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProjectDetailSerializer(detail).data)
