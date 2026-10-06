"""Session authentication (P1-25): login, CSRF, throttle, logout and the no-user-creation rule."""

import re
from pathlib import Path

import pytest
from django.core.cache import cache
from django.test import Client

from api.views.auth import INVALID_LOGIN

BACKEND_DIR = Path(__file__).resolve().parent.parent
PASSWORD = "x-not-a-secret-1"
CREDENTIALS = {"username": "tester", "password": PASSWORD}


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="tester", password=PASSWORD)


@pytest.fixture
def csrf_client():
    """A client that enforces CSRF like a browser, holding a token from /api/auth/csrf/."""
    client = Client(enforce_csrf_checks=True)
    assert client.get("/api/auth/csrf/").status_code == 204
    return client


def post_json(client, path, data=None, token=True):
    headers = {}
    if token:
        headers["HTTP_X_CSRFTOKEN"] = client.cookies["csrftoken"].value
    return client.post(path, data or {}, content_type="application/json", **headers)


def test_csrf_endpoint_sets_the_cookie_and_returns_204(csrf_client):
    assert csrf_client.cookies["csrftoken"].value


@pytest.mark.django_db
def test_login_returns_the_username_and_sets_a_lax_httponly_session_cookie(user, csrf_client):
    response = post_json(csrf_client, "/api/auth/login/", CREDENTIALS)
    assert response.status_code == 200
    assert response.json() == {"username": "tester"}
    cookie = response.cookies["sessionid"]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"


@pytest.mark.django_db
def test_login_cycles_the_session_key_and_rotates_the_csrf_token(user, csrf_client):
    # Plant a session before login so the key before and after can be compared.
    session = csrf_client.session
    session["pre-login"] = "x"
    session.save()
    csrf_client.cookies["sessionid"] = session.session_key
    before_session = csrf_client.cookies["sessionid"].value
    before_token = csrf_client.cookies["csrftoken"].value

    assert post_json(csrf_client, "/api/auth/login/", CREDENTIALS).status_code == 200

    assert csrf_client.cookies["sessionid"].value != before_session
    assert csrf_client.cookies["csrftoken"].value != before_token


@pytest.mark.django_db
def test_login_without_a_csrf_token_is_403(user):
    client = Client(enforce_csrf_checks=True)
    response = post_json(client, "/api/auth/login/", CREDENTIALS, token=False)
    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF failed."}
    assert response["Content-Type"] == "application/json"
    assert "sessionid" not in response.cookies


@pytest.mark.django_db
def test_login_with_a_wrong_csrf_token_is_403(user, csrf_client):
    response = csrf_client.post(
        "/api/auth/login/",
        CREDENTIALS,
        content_type="application/json",
        HTTP_X_CSRFTOKEN="not-the-token",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_session_post_without_a_csrf_token_is_403_not_501(user, csrf_client):
    assert post_json(csrf_client, "/api/auth/login/", CREDENTIALS).status_code == 200
    response = post_json(csrf_client, "/api/captures/", {"text": "x"}, token=False)
    assert response.status_code == 403
    with_token = post_json(csrf_client, "/api/captures/", {"text": "x"})
    assert with_token.status_code != 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data",
    [
        {"username": "tester", "password": "wrong"},
        {"username": "nobody", "password": PASSWORD},
        {"username": "tester"},
        {},
    ],
)
def test_bad_credentials_are_400_with_one_generic_detail(user, csrf_client, data):
    response = post_json(csrf_client, "/api/auth/login/", data)
    assert response.status_code == 400
    assert response.json() == {"detail": INVALID_LOGIN}
    assert "sessionid" not in response.cookies


@pytest.mark.django_db
def test_inactive_user_gets_the_same_400(user, csrf_client):
    user.is_active = False
    user.save()
    response = post_json(csrf_client, "/api/auth/login/", CREDENTIALS)
    assert response.status_code == 400
    assert response.json() == {"detail": INVALID_LOGIN}


@pytest.mark.django_db
def test_sixth_login_attempt_in_a_minute_is_429(user, csrf_client):
    wrong = {"username": "tester", "password": "wrong"}
    for _ in range(5):
        assert post_json(csrf_client, "/api/auth/login/", wrong).status_code == 400
    response = post_json(csrf_client, "/api/auth/login/", CREDENTIALS)
    assert response.status_code == 429


@pytest.mark.django_db
def test_throttle_ignores_x_forwarded_for(user, csrf_client):
    wrong = {"username": "tester", "password": "wrong"}
    for index in range(5):
        response = csrf_client.post(
            "/api/auth/login/",
            wrong,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_client.cookies["csrftoken"].value,
            HTTP_X_FORWARDED_FOR=f"10.0.0.{index}",
        )
        assert response.status_code == 400
    response = csrf_client.post(
        "/api/auth/login/",
        wrong,
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_client.cookies["csrftoken"].value,
        HTTP_X_FORWARDED_FOR="10.0.0.99",
    )
    assert response.status_code == 429


@pytest.mark.django_db
def test_me_returns_the_username_after_login(user, csrf_client):
    post_json(csrf_client, "/api/auth/login/", CREDENTIALS)
    response = csrf_client.get("/api/auth/me/")
    assert response.status_code == 200
    assert response.json() == {"username": "tester"}


@pytest.mark.django_db
def test_logout_clears_the_session(user, csrf_client):
    post_json(csrf_client, "/api/auth/login/", CREDENTIALS)
    assert csrf_client.get("/api/auth/me/").status_code == 200

    assert post_json(csrf_client, "/api/auth/logout/").status_code == 204

    assert csrf_client.get("/api/auth/me/").status_code in {401, 403}


@pytest.mark.django_db
def test_logout_without_a_csrf_token_is_403_and_keeps_the_session(user, csrf_client):
    post_json(csrf_client, "/api/auth/login/", CREDENTIALS)
    assert post_json(csrf_client, "/api/auth/logout/", token=False).status_code == 403
    assert csrf_client.get("/api/auth/me/").status_code == 200


@pytest.mark.django_db
def test_logout_when_anonymous_is_rejected(client):
    assert client.post("/api/auth/logout/").status_code in {401, 403}


# --- no user is ever created from the environment ---------------------------------------------

CREATION_PATTERN = re.compile(
    r"DJANGO_SUPERUSER|createsuperuser|create_superuser|create_user|User\.objects\.create"
)


def test_no_backend_code_creates_users():
    offenders = []
    for path in BACKEND_DIR.rglob("*.py"):
        relative = path.relative_to(BACKEND_DIR)
        if relative.parts[0] in {"tests", ".venv"} or "migrations" in relative.parts:
            continue
        if CREATION_PATTERN.search(path.read_text()):
            offenders.append(str(relative))
    assert offenders == []


@pytest.mark.django_db
def test_password_whitespace_is_significant(django_user_model, csrf_client):
    django_user_model.objects.create_user(username="spacey", password="pw-with-space ")
    trimmed = {"username": "spacey", "password": "pw-with-space"}
    exact = {"username": "spacey", "password": "pw-with-space "}
    assert post_json(csrf_client, "/api/auth/login/", trimmed).status_code == 400
    assert post_json(csrf_client, "/api/auth/login/", exact).status_code == 200


@pytest.mark.django_db
def test_overlong_username_or_password_is_the_generic_400(user, csrf_client):
    for data in (
        {"username": "u" * 151, "password": PASSWORD},
        {"username": "tester", "password": "p" * 4097},
    ):
        response = post_json(csrf_client, "/api/auth/login/", data)
        assert response.status_code == 400
        assert response.json() == {"detail": INVALID_LOGIN}


@pytest.mark.django_db
def test_failed_login_is_logged_without_the_password(user, csrf_client, caplog):
    caplog.set_level("INFO", logger="api.views.auth")
    post_json(csrf_client, "/api/auth/login/", {"username": "u" * 40, "password": "secret-pw-1"})
    post_json(csrf_client, "/api/auth/login/", CREDENTIALS)
    records = [r for r in caplog.records if r.name == "api.views.auth"]
    warnings = [r for r in records if r.levelname == "WARNING"]
    infos = [r for r in records if r.levelname == "INFO"]
    assert len(warnings) == 1 and len(infos) == 1
    assert "secret-pw-1" not in warnings[0].getMessage()
    assert "u" * 33 not in warnings[0].getMessage()
    assert "127.0.0.1" in warnings[0].getMessage()
    assert PASSWORD not in infos[0].getMessage()
