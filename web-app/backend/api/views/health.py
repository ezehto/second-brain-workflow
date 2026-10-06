"""Liveness."""

import logging

from django.db import Error as DatabaseError
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from api.serializers import HealthSerializer

logger = logging.getLogger(__name__)


@extend_schema(
    operation_id="health",
    tags=["health"],
    summary="Liveness and database reachability",
    responses={200: HealthSerializer, 503: HealthSerializer},
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    """Liveness plus database reachability. The body never says more than ok or error."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        logger.warning("health check: database unreachable", exc_info=True)
        return Response({"status": "error"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({"status": "ok"})
