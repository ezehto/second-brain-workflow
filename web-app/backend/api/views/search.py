"""Full-text search (plan section 2.5, design section F): `simple` full text plus trigram titles."""

import re

from django.contrib.postgres.search import (
    SearchHeadline,
    SearchQuery,
    SearchRank,
    TrigramSimilarity,
)
from django.db.models import F, Q
from django.db.models.functions import Left
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import (
    ErrorSerializer,
    SearchQuerySerializer,
    SearchResponseSerializer,
    SearchResultSerializer,
)
from vault.models import SEARCH_BODY_LIMIT, Note

RESULT_LIMIT = 50
SNIPPET_LIMIT = 200
TITLE_SIMILARITY = 0.3
_WHITESPACE = re.compile(r"\s+")


def search_notes(text: str) -> list[dict]:
    """Notes matching `text`, best first, at most `RESULT_LIMIT`, as `SearchResult` dicts.

    A note matches when its search vector matches or its title is trigram-similar. The vector
    is built with `/` turned into a space (models.py), so the query gets the same treatment
    and a path fragment such as `Work/Projects` finds the folder's notes.
    """
    query = SearchQuery(text.replace("/", " "), config="simple", search_type="plain")
    notes = (
        Note.objects.annotate(
            rank=SearchRank(F("search_vector"), query),
            similarity=TrigramSimilarity("title", text),
            headline=SearchHeadline(
                Left("body", SEARCH_BODY_LIMIT),
                query,
                config="simple",
                start_sel="",
                stop_sel="",
                max_fragments=1,
                min_words=10,
                max_words=30,
            ),
        )
        .filter(Q(search_vector=query) | Q(similarity__gt=TITLE_SIMILARITY))
        .order_by("-rank", "-similarity", "path")
        .values("path", "type", "title", "project", "headline")[:RESULT_LIMIT]
    )
    return [
        {
            "path": note["path"],
            "type": note["type"],
            "title": note["title"],
            "project": note["project"],
            "snippet": _WHITESPACE.sub(" ", note["headline"] or "").strip()[:SNIPPET_LIMIT],
            "source": "vault",
        }
        for note in notes
    ]


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
        responses={200: SearchResponseSerializer, 400: ErrorSerializer},
    )
    def get(self, request: Request) -> Response:
        params = SearchQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        text = params.validated_data["q"]
        results = SearchResultSerializer(search_notes(text), many=True).data
        return Response({"query": text, "results": results})
