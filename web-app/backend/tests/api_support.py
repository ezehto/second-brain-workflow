"""Shared pieces of the read-endpoint tests (P1-26): one indexed golden vault per module.

Registered as a plugin by `conftest.py`, so its fixtures (`golden_index`, `api`, `pinned_today`)
need no import.

The expectations come from the fixture's `expected/index.json` and from the modification times
this module assigns, never from the code under test.
"""

import json
import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from django.utils import timezone

from vault import indexer
from vault.models import IndexPass, Note, Tag

GOLDEN = Path(__file__).resolve().parents[3] / "second-brain/fixtures/golden-vault"
OPENAPI = Path(__file__).resolve().parent.parent / "openapi.yaml"
EXPECTED = json.loads((GOLDEN / "expected/index.json").read_text())["notes"]
REFERENCE_DATE = "2026-10-09"

# Every file gets one of four modification times, so `-modified` has many ties to break by path.
BASE_MTIME = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
MTIME_STEP = timedelta(minutes=7)


def assigned_mtime(position: int) -> datetime:
    return BASE_MTIME + MTIME_STEP * (position % 4)


MTIMES = {path: assigned_mtime(i) for i, path in enumerate(sorted(EXPECTED))}


def by_bytes(path: str) -> bytes:
    """Sort key matching the API's `C` collation on paths."""
    return path.encode()


def stem(path: str) -> str:
    return path.rpartition("/")[2].removesuffix(".md")


@pytest.fixture(scope="module")
def golden_index(django_db_setup, django_db_blocker, tmp_path_factory):
    """A copy of the golden vault, indexed once and committed for the whole module."""
    root = tmp_path_factory.mktemp("golden") / "vault"
    shutil.copytree(GOLDEN / "vault", root)
    for path, moment in MTIMES.items():
        os.utime(root / path, (moment.timestamp(), moment.timestamp()))
    with django_db_blocker.unblock():
        indexer.sync(root)
        yield root
        Note.objects.all().delete()
        Tag.objects.all().delete()
        IndexPass.objects.all().delete()


@pytest.fixture
def api(client, django_user_model, pinned_today):
    """A logged-in test client, with today pinned to the reference date."""
    user = django_user_model.objects.create_user(username="tester", password="x-not-a-secret-1")
    client.force_login(user)
    return client


@pytest.fixture
def pinned_today(monkeypatch):
    """The fixture's reference date, whatever the container's environment says."""
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    monkeypatch.setenv("SECOND_BRAIN_TODAY", REFERENCE_DATE)


def freeze_utc(monkeypatch, moment: datetime) -> None:
    """Real clock at `moment` (UTC) with no pinned date: "today" is then the Manila date."""
    monkeypatch.delenv("SECOND_BRAIN_TEST_MODE", raising=False)
    monkeypatch.delenv("SECOND_BRAIN_TODAY", raising=False)
    monkeypatch.setattr(timezone, "now", lambda: moment)


def schema_properties(component: str) -> set[str]:
    """The property names of a component of the committed OpenAPI document."""
    document = yaml.safe_load(OPENAPI.read_text())
    return set(document["components"]["schemas"][component]["properties"])
