"""The OpenAPI contract (P1-24): the committed schema, its coverage of plan section 5, and auth."""

from pathlib import Path

import pytest
import yaml
from django.core.management import call_command

from api.serializers import (
    CreateNoteRequestSerializer,
    StatusChangeRequestSerializer,
    TriageRequestSerializer,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent
COMMITTED_SCHEMA = BACKEND_DIR / "openapi.yaml"

# Plan section 5, every method and path.
SECTION_5 = [
    ("get", "/api/health/"),
    ("get", "/api/auth/csrf/"),
    ("post", "/api/auth/login/"),
    ("post", "/api/auth/logout/"),
    ("get", "/api/auth/me/"),
    ("get", "/api/notes/"),
    ("get", "/api/notes/lookup/"),
    ("post", "/api/notes/"),
    ("post", "/api/notes/status/"),
    ("post", "/api/captures/"),
    ("post", "/api/captures/triage/"),
    ("get", "/api/projects/"),
    ("get", "/api/projects/{slug}/"),
    ("get", "/api/standups/today/"),
    ("post", "/api/standups/today/"),
    ("post", "/api/standups/today/append/"),
    ("get", "/api/dashboard/"),
    ("get", "/api/search/"),
    ("get", "/api/index/status/"),
    ("post", "/api/index/refresh/"),
    ("get", "/api/schema/"),
]

NO_SESSION_PATHS = {"/api/health/", "/api/auth/csrf/", "/api/auth/login/"}
# Served for real: P1-24 (health, schema) and P1-25 (auth).
IMPLEMENTED = {
    ("get", "/api/health/"),
    ("get", "/api/schema/"),
    ("get", "/api/auth/csrf/"),
    ("post", "/api/auth/login/"),
    ("post", "/api/auth/logout/"),
    ("get", "/api/auth/me/"),
    ("get", "/api/search/"),
    ("get", "/api/index/status/"),
    ("post", "/api/index/refresh/"),
    ("get", "/api/notes/"),
    ("get", "/api/notes/lookup/"),
    ("get", "/api/projects/"),
    ("get", "/api/projects/{slug}/"),
    ("get", "/api/dashboard/"),
    ("post", "/api/notes/"),
    ("post", "/api/notes/status/"),
    ("post", "/api/captures/"),
    ("post", "/api/captures/triage/"),
    ("get", "/api/standups/today/"),
    ("post", "/api/standups/today/"),
    ("post", "/api/standups/today/append/"),
}
STUBBED = [entry for entry in SECTION_5 if entry not in IMPLEMENTED]
STUBBED_SESSION = [entry for entry in STUBBED if entry[1] not in NO_SESSION_PATHS]


def session_operations() -> list[tuple[str, str]]:
    """Every (method, path) the committed schema secures with the session cookie."""
    document = yaml.safe_load(COMMITTED_SCHEMA.read_text())
    return [
        (method, path)
        for path, item in document["paths"].items()
        for method, operation in item.items()
        if operation.get("security") == [{"cookieAuth": []}]
    ]


def generate_schema(tmp_path: Path) -> str:
    target = tmp_path / "generated.yaml"
    call_command("spectacular", file=str(target), validate=True, fail_on_warn=True)
    return target.read_text()


@pytest.fixture(scope="module")
def schema_document(tmp_path_factory):
    text = generate_schema(tmp_path_factory.mktemp("schema"))
    return yaml.safe_load(text)


def concrete_path(template: str) -> str:
    return template.replace("{slug}", "sample-project")


def request_for(client, method: str, path: str):
    return getattr(client, method)(concrete_path(path), content_type="application/json")


def test_committed_schema_equals_generated_output(tmp_path):
    assert COMMITTED_SCHEMA.read_text() == generate_schema(tmp_path)


def test_schema_covers_exactly_section_5(schema_document):
    in_schema = {
        (method, path)
        for path, item in schema_document["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert in_schema == set(SECTION_5)


@pytest.mark.parametrize(("method", "path"), SECTION_5)
def test_session_auth_declared_except_health_csrf_login(schema_document, method, path):
    operation = schema_document["paths"][path][method]
    if path in NO_SESSION_PATHS:
        # `[{}]` is OpenAPI's "no authentication"; an absent or empty list means the same.
        assert all(not requirement for requirement in operation.get("security", []))
    else:
        assert operation["security"] == [{"cookieAuth": []}]
    assert schema_document["components"]["securitySchemes"]["cookieAuth"]["in"] == "cookie"


@pytest.mark.parametrize(("method", "path"), STUBBED_SESSION)
@pytest.mark.django_db
def test_unimplemented_endpoint_is_501_when_authenticated(client, django_user_model, method, path):
    user = django_user_model.objects.create_user(username="tester", password="x-not-a-secret-1")
    client.force_login(user)
    response = request_for(client, method, path)
    assert response.status_code == 501
    assert response.json() == {"detail": "Not implemented"}


@pytest.mark.parametrize(("method", "path"), session_operations())
@pytest.mark.django_db
def test_session_endpoint_rejects_anonymous(client, method, path):
    assert request_for(client, method, path).status_code in {401, 403}


@pytest.mark.django_db
def test_schema_endpoint_serves_document_to_logged_in_client(client, django_user_model):
    user = django_user_model.objects.create_user(username="tester", password="x-not-a-secret-1")
    client.force_login(user)
    response = client.get("/api/schema/")
    assert response.status_code == 200
    assert b"openapi: 3." in response.content


@pytest.mark.django_db
def test_schema_endpoint_rejects_anonymous(client):
    assert client.get("/api/schema/").status_code in {401, 403}


# --- request serializer rules ----------------------------------------------------------------

GOOD_HASH = "a" * 64


@pytest.mark.parametrize(
    ("note_type", "status", "valid"),
    [
        ("task", "in-progress", True),
        ("task", "accepted", False),
        ("decision", "accepted", True),
        ("decision", "done", False),
        ("project", "archived", True),
        ("lesson", "paused", False),
        ("lesson", None, True),
    ],
)
def test_create_request_checks_status_against_the_type(note_type, status, valid):
    data = {"type": note_type, "title": "A title"}
    if status:
        data["status"] = status
    serializer = CreateNoteRequestSerializer(data=data)
    assert serializer.is_valid() is valid
    if not valid:
        assert "status" in serializer.errors


def test_create_request_rejects_a_type_that_cannot_be_created():
    assert not CreateNoteRequestSerializer(data={"type": "capture", "title": "x"}).is_valid()


@pytest.mark.parametrize(
    ("action", "classification", "valid"),
    [
        ("dismiss", None, True),
        ("dismiss", "thought", True),
        ("task", None, False),
        ("keep", None, False),
        ("task", "task", True),
        ("keep", "question", True),
        ("task", "not-a-kind", False),
    ],
)
def test_triage_requires_classification_unless_dismiss(action, classification, valid):
    data = {"path": "00-Inbox/x.md", "expected_hash": GOOD_HASH, "action": action}
    if classification:
        data["classification"] = classification
    serializer = TriageRequestSerializer(data=data)
    assert serializer.is_valid() is valid
    if action != "dismiss" and classification is None:
        assert "classification" in serializer.errors


@pytest.mark.parametrize("bad_hash", ["", "abc", "A" * 64, "g" * 64, "a" * 65])
def test_expected_hash_must_be_a_lowercase_sha256_digest(bad_hash):
    serializer = StatusChangeRequestSerializer(
        data={"path": "a.md", "status": "done", "expected_hash": bad_hash}
    )
    assert not serializer.is_valid()
    assert "expected_hash" in serializer.errors


def test_path_is_limited_to_200_characters():
    data = {"path": "a" * 201, "status": "done", "expected_hash": GOOD_HASH}
    serializer = StatusChangeRequestSerializer(data=data)
    assert not serializer.is_valid()
    assert "path" in serializer.errors


def test_page_size_bounds_are_in_the_schema(schema_document):
    parameters = schema_document["paths"]["/api/notes/"]["get"]["parameters"]
    page_size = next(p for p in parameters if p["name"] == "page_size")["schema"]
    assert (page_size["minimum"], page_size["maximum"]) == (1, 200)


def test_standup_branches_discriminate_on_exists(schema_document):
    schemas = schema_document["components"]["schemas"]
    for branch, value in (("StandupExisting", True), ("StandupMissing", False)):
        exists = schemas[branch]["properties"]["exists"]
        if "$ref" in exists:
            exists = schemas[exists["$ref"].rsplit("/", 1)[1]]
        assert exists["enum"] == [value]
