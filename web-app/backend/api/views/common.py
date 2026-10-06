"""Helpers shared by the view modules."""

from rest_framework import status
from rest_framework.response import Response


def not_implemented() -> Response:
    """The response of an endpoint whose task has not landed yet."""
    return Response({"detail": "Not implemented"}, status=status.HTTP_501_NOT_IMPLEMENTED)
