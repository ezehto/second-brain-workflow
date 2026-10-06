"""Full-text search. Implemented in P1-27."""

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import ErrorSerializer, SearchQuerySerializer, SearchResponseSerializer
from api.views.common import not_implemented


class SearchView(APIView):
    @extend_schema(
        operation_id="search",
        tags=["search"],
        summary="Search the vault",
        description=(
            "Full-text search (`simple` configuration) plus trigram title match. Ties are "
            "ordered by `path`. `400` when `q` is missing or blank. Not paginated."
        ),
        parameters=[SearchQuerySerializer],
        responses={200: SearchResponseSerializer, 400: ErrorSerializer, 501: ErrorSerializer},
    )
    def get(self, request: Request) -> Response:
        return not_implemented()
