"""The test clock (plan section 2.12): one place that decides what "today" is.

The pinned date applies only when SECOND_BRAIN_TEST_MODE=1 and SECOND_BRAIN_TODAY are both
set. Either one alone is ignored with a warning. Environment is read at call time.
"""

import logging
import os
import re
from datetime import date

from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

logger = logging.getLogger(__name__)

TEST_MODE_VAR = "SECOND_BRAIN_TEST_MODE"
TODAY_VAR = "SECOND_BRAIN_TODAY"
DATE_FORMAT = re.compile(r"\d{4}-\d{2}-\d{2}")


def test_mode() -> bool:
    """True only when SECOND_BRAIN_TEST_MODE is exactly "1"."""
    return os.environ.get(TEST_MODE_VAR) == "1"


# pytest would otherwise collect this helper as a test.
test_mode.__test__ = False  # type: ignore[attr-defined]


def pinned_date() -> date | None:
    """The pinned date, or None when test mode is off or no date is set.

    Raises ImproperlyConfigured for an invalid date in test mode. When exactly one of the two
    variables is set it is ignored; warn_if_half_configured() reports that once at startup.
    """
    raw = os.environ.get(TODAY_VAR, "").strip()
    if test_mode() and raw:
        try:
            if not DATE_FORMAT.fullmatch(raw):
                raise ValueError(raw)
            return date.fromisoformat(raw)
        except ValueError:
            raise ImproperlyConfigured(
                f"{TODAY_VAR}={raw!r} is not a valid YYYY-MM-DD date"
            ) from None
    return None


def warn_if_half_configured() -> None:
    """Log a warning when exactly one of the two test-clock variables is set (called at startup)."""
    raw = os.environ.get(TODAY_VAR, "").strip()
    if raw and not test_mode():
        logger.warning("%s is set without %s=1; ignoring it", TODAY_VAR, TEST_MODE_VAR)
    elif test_mode() and not raw:
        logger.warning("%s is set but %s is not; ignoring it", TEST_MODE_VAR, TODAY_VAR)


def today() -> date:
    """The pinned date in test mode, otherwise today's date in TIME_ZONE."""
    return pinned_date() or timezone.localdate()
