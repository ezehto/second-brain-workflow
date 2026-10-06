"""GET /api/health/."""

import pytest
from django.db import OperationalError, connection


@pytest.mark.django_db
def test_health_ok(client):
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_503_when_database_is_down(client, monkeypatch):
    def boom(*args, **kwargs):
        raise OperationalError("connection refused")

    monkeypatch.setattr(connection, "cursor", boom)
    response = client.get("/api/health/")
    assert response.status_code == 503
    assert response.json() == {"status": "error"}


def test_health_needs_no_session_and_rejects_writes(client):
    assert client.post("/api/health/").status_code == 405


def test_unknown_api_path_is_not_served(client):
    assert client.get("/api/nope/").status_code == 404
