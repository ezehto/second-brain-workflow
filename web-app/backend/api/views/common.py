"""Helpers shared by the view modules."""

from rest_framework import status
from rest_framework.response import Response


def not_implemented() -> Response:
    """The response of an endpoint whose task has not landed yet."""
    return Response({"detail": "Not implemented"}, status=status.HTTP_501_NOT_IMPLEMENTED)


def _messages(errors, prefix: str = "") -> list[str]:
    """Flatten nested serializer errors (dicts keyed by field or list index, lists) to text."""
    if isinstance(errors, dict):
        return [
            message
            for key, value in errors.items()
            for message in _messages(
                value, f"{prefix}{key}: " if not str(key).isdigit() else prefix
            )
        ]
    if isinstance(errors, list | tuple):
        return [message for item in errors for message in _messages(item, prefix)]
    return [f"{prefix}{errors}"]


def validation_detail(errors: dict) -> dict[str, str]:
    """A serializer's field errors as the API's `{"detail": ...}` error body."""
    return {"detail": "; ".join(_messages(errors))}
