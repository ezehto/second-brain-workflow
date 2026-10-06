"""`manage.py sync_vault [--watch]`: index the vault (plan 2.7, task P1-21)."""

import signal
import threading
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from vault import indexer


class Command(BaseCommand):
    help = "Run one indexer pass over the vault, or keep passing every INDEXER_POLL_SECONDS."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--watch", action="store_true", help="loop until SIGTERM or SIGINT")

    def handle(self, *args, **options) -> None:
        root = Path(settings.VAULT_ROOT)
        if options["watch"]:
            stop = threading.Event()
            for number in (signal.SIGTERM, signal.SIGINT):
                signal.signal(number, lambda *_: stop.set())
            indexer.watch(root, settings.INDEXER_POLL_SECONDS, stop_event=stop)
            return
        with indexer.quiet_info():
            summary = indexer.sync(root)
        self.stdout.write(summary.to_json())
