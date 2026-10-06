"""Session authentication: CSRF cookie, login, logout and the current user."""

import logging

from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from api.serializers import ErrorSerializer, LoginRequestSerializer, MeSerializer

# One message for every failed login, so a response never says which field was wrong.
logger = logging.getLogger(__name__)

INVALID_LOGIN = "Invalid username or password."


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="auth_csrf",
        tags=["auth"],
        auth=[],
        summary="Set the CSRF cookie",
        description="Sets the `csrftoken` cookie. No body is returned.",
        responses={204: None},
    )
    def get(self, request: Request) -> Response:
        return Response(status=status.HTTP_204_NO_CONTENT)


# APIView.as_view() is csrf-exempt and SessionAuthentication only checks CSRF for authenticated
# users, so an anonymous login POST needs csrf_protect applied explicitly.
@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    """Session login.

    Throttle: 5 attempts a minute per REMOTE_ADDR (NUM_PROXIES = 0, so X-Forwarded-For is
    ignored). The counter lives in the per-process locmem cache, which is right for the
    single-worker dev server only. Once a client is logged in, further login POSTs are keyed
    by user instead of address. Behind the Vite proxy every client shares one bucket, which is
    acceptable on 127.0.0.1.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

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
            403: ErrorSerializer,
            429: ErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = LoginRequestSerializer(data=request.data)
        user = None
        attempted = ""
        if serializer.is_valid():
            attempted = serializer.validated_data["username"][:32]
            user = authenticate(request, **serializer.validated_data)
        if user is None:
            logger.warning(
                "Failed login from %s for username %r", request.META.get("REMOTE_ADDR"), attempted
            )
            return Response({"detail": INVALID_LOGIN}, status=status.HTTP_400_BAD_REQUEST)
        logger.info("Login from %s for user id %s", request.META.get("REMOTE_ADDR"), user.pk)
        login(request, user)  # cycles the session key and rotates the CSRF token
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    @extend_schema(
        operation_id="auth_logout",
        tags=["auth"],
        summary="End the session",
        request=None,
        responses={204: None},
    )
    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(
        operation_id="auth_me",
        tags=["auth"],
        summary="Current user name",
        responses={200: MeSerializer},
    )
    def get(self, request: Request) -> Response:
        return Response(MeSerializer(request.user).data)
