"""Permission matrix (P1-30): every operation in `openapi.yaml`, three ways.

* anonymous: 401/403 for every session-secured operation, the real answer for the three open ones
* a session with no CSRF token: 403 on every unsafe method, login included
* a valid session with a CSRF token: never 401/403 (any other status is fine, 501 included)
"""

import pytest
import yaml
from api_support import OPENAPI
from django.core.cache import cache
from django.test import Client

PASSWORD = "x-not-a-secret-1"
SLUG = "harbor-lights"
HASH = "0" * 64
METHODS = {"get", "post", "put", "patch", "delete"}
SAFE = {"get"}
AUTH_STATUSES = {401, 403}

# Minimal valid input per operation, so a 400 never stands in for the auth result.
BODIES = {
    ("post", "/api/auth/login/"): {"username": "tester", "password": PASSWORD},
    ("post", "/api/notes/"): {"type": "task", "title": "Permission probe"},
    ("post", "/api/notes/status/"): {"path": "a.md", "expected_hash": HASH, "status": "done"},
    ("post", "/api/captures/"): {"text": "Permission probe"},
    ("post", "/api/captures/triage/"): {"path": "a.md", "expected_hash": HASH, "action": "dismiss"},
    ("post", "/api/standups/today/append/"): {
        "section": "Today",
        "text": "x",
        "expected_hash": HASH,
    },
}
PARAMS = {
    ("get", "/api/notes/lookup/"): {"path": "a.md"},
    ("get", "/api/search/"): {"q": "lantern"},
}
# What an anonymous caller gets from the three operations that need no session.
OPEN = {
    ("get", "/api/health/"): 200,
    ("get", "/api/auth/csrf/"): 204,
    ("post", "/api/auth/login/"): 200,
}

pytestmark = pytest.mark.django_db


def schema_operations() -> list[tuple[str, str]]:
    """Every (method, path) of the committed schema, secured or not."""
    document = yaml.safe_load(OPENAPI.read_text())
    return sorted(
        (method, path)
        for path, item in document["paths"].items()
        for method in item
        if method in METHODS
    )


OPERATIONS = schema_operations()
SECURED = [op for op in OPERATIONS if op not in OPEN]
UNSAFE = [op for op in OPERATIONS if op[0] not in SAFE]


def ids(operations):
    return [f"{method.upper()} {path}" for method, path in operations]


@pytest.fixture(autouse=True)
def clean_throttle():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="tester", password=PASSWORD)


def send(client, method, path, token=None):
    """One request for an operation, with a minimal valid body or query."""
    url = path.replace("{slug}", SLUG)
    extra = {"HTTP_X_CSRFTOKEN": token} if token else {}
    if method in SAFE:
        return getattr(client, method)(url, PARAMS.get((method, path), {}), **extra)
    body = BODIES.get((method, path), {})
    return getattr(client, method)(url, body, content_type="application/json", **extra)


def csrf_client():
    """A client enforcing CSRF like a browser, holding a token from `/api/auth/csrf/`."""
    client = Client(enforce_csrf_checks=True)
    assert client.get("/api/auth/csrf/").status_code == 204
    return client, client.cookies["csrftoken"].value


def test_the_matrix_covers_exactly_the_schema_operations():
    document = yaml.safe_load(OPENAPI.read_text())
    assert len(OPERATIONS) == 21
    assert len(SECURED) == 18
    secured = {
        (method, path)
        for path, item in document["paths"].items()
        for method, operation in item.items()
        if method in METHODS and operation.get("security") == [{"cookieAuth": []}]
    }
    assert set(SECURED) == secured  # exactly the three open operations are not cookieAuth


@pytest.mark.parametrize(("method", "path"), SECURED, ids=ids(SECURED))
def test_anonymous_is_refused_on_every_secured_operation(user, method, path):
    client, token = csrf_client()
    assert send(client, method, path, token).status_code in AUTH_STATUSES
    assert send(Client(), method, path).status_code in AUTH_STATUSES  # and without any token


@pytest.mark.parametrize(("method", "path"), list(OPEN), ids=ids(OPEN))
def test_open_operations_answer_anonymous(user, method, path):
    client, token = csrf_client()
    response = send(client, method, path, token)
    assert response.status_code == OPEN[(method, path)]


@pytest.mark.parametrize(("method", "path"), UNSAFE, ids=ids(UNSAFE))
def test_a_session_without_a_csrf_token_is_refused_on_every_unsafe_method(user, method, path):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    response = send(client, method, path)
    assert response.status_code == 403
    assert b"CSRF" in response.content


@pytest.mark.parametrize(("method", "path"), OPERATIONS, ids=ids(OPERATIONS))
def test_a_valid_session_with_a_token_is_never_refused_as_unauthenticated(user, method, path):
    client, token = csrf_client()
    login = send(client, "post", "/api/auth/login/", token)
    assert login.status_code == 200
    token = client.cookies["csrftoken"].value  # login rotates the token
    response = send(client, method, path, token)
    assert response.status_code not in AUTH_STATUSES, response.content
    assert response.status_code != 500
