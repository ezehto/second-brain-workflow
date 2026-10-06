"""vault.clock.today(): plan section 2.12."""

import logging
from datetime import date

import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from vault import clock

PINNED = date(2026, 10, 9)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("SECOND_BRAIN_TEST_MODE", raising=False)
    monkeypatch.delenv("SECOND_BRAIN_TODAY", raising=False)


def test_both_variables_pin_the_date(monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    monkeypatch.setenv("SECOND_BRAIN_TODAY", "2026-10-09")
    assert clock.today() == PINNED
    assert clock.pinned_date() == PINNED
    assert clock.test_mode() is True


def test_date_alone_is_ignored_and_today_stays_silent(monkeypatch, caplog):
    monkeypatch.setenv("SECOND_BRAIN_TODAY", "2026-10-09")
    with caplog.at_level(logging.WARNING, logger="vault.clock"):
        assert clock.today() == timezone.localdate()
        assert clock.today() == timezone.localdate()
    assert clock.pinned_date() is None
    assert clock.test_mode() is False
    assert caplog.text == ""


def test_test_mode_alone_is_ignored(monkeypatch, caplog):
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    with caplog.at_level(logging.WARNING, logger="vault.clock"):
        assert clock.today() == timezone.localdate()
    assert clock.pinned_date() is None
    assert caplog.text == ""


def test_startup_warns_once_for_date_alone(monkeypatch, caplog):
    monkeypatch.setenv("SECOND_BRAIN_TODAY", "2026-10-09")
    with caplog.at_level(logging.WARNING, logger="vault.clock"):
        apps.get_app_config("vault").ready()
    assert caplog.text.count("SECOND_BRAIN_TODAY") == 1


def test_startup_warns_for_test_mode_alone(monkeypatch, caplog):
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    with caplog.at_level(logging.WARNING, logger="vault.clock"):
        clock.warn_if_half_configured()
    assert "SECOND_BRAIN_TEST_MODE" in caplog.text


BOTH = {"SECOND_BRAIN_TEST_MODE": "1", "SECOND_BRAIN_TODAY": "2026-10-09"}


@pytest.mark.parametrize("env", [{}, BOTH])
def test_startup_is_silent_when_both_or_neither(monkeypatch, caplog, env):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    with caplog.at_level(logging.WARNING, logger="vault.clock"):
        clock.warn_if_half_configured()
    assert caplog.text == ""


def test_test_mode_must_be_exactly_one(monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "true")
    monkeypatch.setenv("SECOND_BRAIN_TODAY", "2026-10-09")
    assert clock.test_mode() is False
    assert clock.today() == timezone.localdate()


def test_neither_variable_uses_current_date_without_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="vault.clock"):
        assert clock.today() == timezone.localdate()
    assert caplog.text == ""


@pytest.mark.parametrize("bad", ["2026-13-01", "tomorrow", "20261009", "2026-02-30"])
def test_invalid_date_in_test_mode_raises(monkeypatch, bad):
    monkeypatch.setenv("SECOND_BRAIN_TEST_MODE", "1")
    monkeypatch.setenv("SECOND_BRAIN_TODAY", bad)
    with pytest.raises(ImproperlyConfigured):
        clock.today()
    with pytest.raises(ImproperlyConfigured):
        clock.pinned_date()


def test_invalid_date_without_test_mode_is_only_ignored(monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_TODAY", "not-a-date")
    assert clock.today() == timezone.localdate()


def test_current_date_follows_time_zone(settings, monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    # 2026-10-09 20:00 UTC is already 10-10 in Manila (UTC+8) and still 10-09 in Honolulu.
    instant = datetime(2026, 10, 9, 20, 0, tzinfo=ZoneInfo("UTC"))
    monkeypatch.setattr(timezone, "now", lambda: instant)
    settings.TIME_ZONE = "Asia/Manila"
    timezone.activate("Asia/Manila")
    try:
        assert clock.today() == date(2026, 10, 10)
        timezone.activate("Pacific/Honolulu")
        assert clock.today() == date(2026, 10, 9)
    finally:
        timezone.deactivate()
