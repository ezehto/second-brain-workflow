"""Session authentication. Login, logout and the CSRF cookie are implemented in P1-25."""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import ErrorSerializer, LoginRequestSerializer, MeSerializer
from api.views.common import not_implemented


class CsrfView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="auth_csrf",
        tags=["auth"],
        auth=[],
        summary="Set the CSRF cookie",
        description="Sets the `csrftoken` cookie. No body is returned.",
        responses={204: None, 501: ErrorSerializer},
    )
    def get(self, request: Request) -> Response:
        return not_implemented()


class LoginView(APIView):
    # P1-25: add csrf_protect here (APIView is csrf-exempt and SessionAuthentication only checks
    # CSRF for authenticated users), ensure_csrf_cookie on CsrfView, the 5/min throttle scope,
    # and a test with Client(enforce_csrf_checks=True).
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="auth_login",
        tags=["auth"],
        auth=[],
        summary="Session login",
        description=(
            "Starts a session. No session is needed, but **CSRF is required**: send the "
            "`X-CSRFToken` header with the value of the cookie set by `GET /api/auth/csrf/`. "
            "Throttled to 5 attempts per minute. A wrong username or password gives the same "
            "400 either way."
        ),
        request=LoginRequestSerializer,
        responses={
            200: MeSerializer,
            400: ErrorSerializer,
            429: ErrorSerializer,
            501: ErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        return not_implemented()


class LogoutView(APIView):
    @extend_schema(
        operation_id="auth_logout",
        tags=["auth"],
        summary="End the session",
        request=None,
        responses={204: None, 501: ErrorSerializer},
    )
    def post(self, request: Request) -> Response:
        return not_implemented()


class MeView(APIView):
    @extend_schema(
        operation_id="auth_me",
        tags=["auth"],
        summary="Current user name",
        responses={200: MeSerializer, 501: ErrorSerializer},
    )
    def get(self, request: Request) -> Response:
        return not_implemented()
