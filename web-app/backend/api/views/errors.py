"""Error responses that Django renders outside DRF."""

from django.http import HttpRequest, JsonResponse


def csrf_failure(request: HttpRequest, reason: str = "") -> JsonResponse:
    """CSRF_FAILURE_VIEW: a JSON 403 in the API's error shape. The reason is not exposed."""
    return JsonResponse({"detail": "CSRF failed."}, status=403)
