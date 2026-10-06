"""`manage.py reindex`: rebuild the index from the vault (plan 2.9, task P1-21)."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from vault import indexer


class Command(BaseCommand):
    help = "Empty the Note, Link and Tag tables and index every note again."

    def handle(self, *args, **options) -> None:
        with indexer.quiet_info():
            summary = indexer.reindex(Path(settings.VAULT_ROOT))
        self.stdout.write(summary.to_json())
