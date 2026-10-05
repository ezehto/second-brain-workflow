"""/project scenarios (P1-10, P1-11; plan sections 2.1, 4, 4.1; links.md slug rule).

Plan 4.1: an argument that is exactly an existing project's slug shows that
project's summary and writes nothing; an argument whose slug equals an existing
project's slug is refused, naming the existing note; anything else creates.

Live: one `claude -p` call per test.
"""

import pytest

pytestmark = pytest.mark.commands

NEW_PROJECT = "02-Work/Projects/Tidal Lantern Survey.md"


def test_project_creates_an_active_project_note(sb):
    before, baseline = sb.snapshot(), sb.findings()

    session = sb.run("/project", "Tidal Lantern Survey")

    sb.changes(before, session, added=(NEW_PROJECT,))
    sb.check_new_note(NEW_PROJECT, "project", session, status="active", tags=[])
    sb.assert_no_new_findings(baseline, session)


def test_project_refuses_a_title_whose_slug_clashes_and_names_the_existing_note(sb):
    """`Harbor Lights!` is a new file name but slugifies to `harbor-lights`."""
    before = sb.snapshot()

    session = sb.run("/project", "Harbor Lights!")

    sb.unchanged(before, session)
    text = session.all_text
    # The prompt itself says "Harbor Lights!", so echoing it is not enough.
    names_it = ("harbor-lights" in text.lower() or "Harbor Lights.md" in text
                or "02-Work/Projects/Harbor Lights" in text)
    sb.expect(names_it, "the refusal names neither the existing note nor its slug", session)


def test_project_slug_shows_the_summary_and_writes_nothing(sb):
    before = sb.snapshot()

    session = sb.run("/project", "harbor-lights")

    sb.unchanged(before, session)
    sb.expect("Harbor Lights" in session.all_text, "the summary does not name the project", session)
