"""Tests for the watch loop (plan 2.7, task P1-21)."""

import logging
import signal
import threading

import pytest
from django.core.management import call_command

from vault import indexer
from vault.indexer import Indexer, PassSummary

pytestmark = pytest.mark.django_db


class FakeIndexer(Indexer):
    def __init__(self, behaviours):
        super().__init__()
        self.behaviours = list(behaviours)
        self.calls = 0

    def sync(self, root, *, force=False):
        behaviour = self.behaviours[self.calls % len(self.behaviours)]
        self.calls += 1
        if isinstance(behaviour, Exception):
            raise behaviour
        return PassSummary()


class Time:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_runs_n_passes_with_injected_clock_and_sleep(tmp_path):
    t = Time()
    fake = FakeIndexer([None])
    passes = indexer.watch(tmp_path, 10, clock=t.clock, sleep=t.sleep, max_passes=3, indexer=fake)
    assert passes == fake.calls == 3
    assert t.sleeps == [10, 10]


def test_sleep_is_the_interval_minus_the_pass_time(tmp_path):
    t = Time()

    class Slow(FakeIndexer):
        def sync(self, root, *, force=False):
            t.now += 4
            return super().sync(root)

    indexer.watch(tmp_path, 10, clock=t.clock, sleep=t.sleep, max_passes=2, indexer=Slow([None]))
    assert t.sleeps == [6]


def test_a_failing_pass_is_logged_and_the_loop_continues(tmp_path, caplog):
    t = Time()
    fake = FakeIndexer([RuntimeError("boom"), None])
    with caplog.at_level(logging.ERROR, logger="vault.indexer"):
        passes = indexer.watch(
            tmp_path, 1, clock=t.clock, sleep=t.sleep, max_passes=3, indexer=fake
        )
    assert passes == 3
    assert "indexer pass failed" in caplog.text and "boom" in caplog.text


def test_an_over_budget_pass_warns(isolated_vault, monkeypatch, caplog):
    monkeypatch.setattr(indexer, "STEADY_BUDGET_SECONDS", -1.0)
    with caplog.at_level(logging.WARNING, logger="vault.indexer"):
        indexer.watch(isolated_vault, 1, sleep=lambda s: None, max_passes=1)
    assert "over the" in caplog.text


def test_stop_event_ends_the_loop(tmp_path):
    stop = threading.Event()
    fake = FakeIndexer([None])

    def sleep(seconds):
        stop.set()

    passes = indexer.watch(tmp_path, 1, sleep=sleep, stop_event=stop, indexer=fake)
    assert passes == 1


def test_sigterm_handler_stops_the_watch_command(isolated_vault, monkeypatch):
    handlers = {}
    monkeypatch.setattr(
        signal, "signal", lambda number, handler: handlers.update({number: handler})
    )
    seen = {}

    def fake_watch(root, interval, *, stop_event):
        seen["interval"] = interval
        assert not stop_event.is_set()
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        assert stop_event.is_set()

    monkeypatch.setattr(indexer, "watch", fake_watch)
    call_command("sync_vault", "--watch")
    assert signal.SIGINT in handlers and seen["interval"] == 10


def test_watch_logs_one_json_line_per_pass(isolated_vault, caplog):
    (isolated_vault / "A.md").write_text("a")
    with caplog.at_level(logging.INFO, logger="vault.indexer"):
        indexer.watch(isolated_vault, 1, sleep=lambda s: None, max_passes=2)
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("{")]
    assert len(lines) == 2 and '"added": 1' in lines[0]
