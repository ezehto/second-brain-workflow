"""/project scenarios (P1-10, P1-11; plan sections 2.1, 4, 4.1; links.md slug rule).

Plan 4.1: an argument that is exactly an existing project's slug shows that
project's summary and writes nothing; an argument whose slug equals an existing
project's slug is refused, naming the existing note; anything else creates.

Live: one `claude -p` call per live test; `test_names_existing_project` is not live.
"""

import re

import pytest

NEW_PROJECT = "02-Work/Projects/Tidal Lantern Survey.md"
CLASH_ARGUMENT = "Harbor Lights!"


def names_existing_project(text):
    """True when a reply names the existing `Harbor Lights` note or its slug, not
    merely the echoed argument `Harbor Lights!`."""
    return "harbor-lights" in text.lower() or re.search(r"Harbor Lights(?!!)", text) is not None


@pytest.mark.parametrize(
    "text, names",
    [
        ("Refused: [[Harbor Lights]] already has this slug.", True),
        ("Refused: 02-Work/Projects/Harbor Lights.md exists.", True),
        ("Refused: the slug harbor-lights is taken.", True),
        ("The project Harbor Lights already exists.", True),
        ("Refused: Harbor Lights! clashes with an existing project.", False),
        ("Refused.", False),
    ],
)
def test_names_existing_project(text, names):
    assert names_existing_project(text) is names


@pytest.mark.commands
def test_project_creates_an_active_project_note(sb):
    before, baseline = sb.snapshot(), sb.findings()

    session = sb.run("/project", "Tidal Lantern Survey")

    sb.changes(before, session, added=(NEW_PROJECT,))
    sb.check_new_note(NEW_PROJECT, "project", session, status="active", tags=[])
    sb.assert_no_new_findings(baseline, session)


@pytest.mark.commands
def test_project_refuses_a_title_whose_slug_clashes_and_names_the_existing_note(sb):
    """`Harbor Lights!` is a new file name but slugifies to `harbor-lights`."""
    before = sb.snapshot()

    session = sb.run("/project", CLASH_ARGUMENT)

    sb.unchanged(before, session)
    sb.expect(names_existing_project(session.all_text),
              "the refusal names neither the existing note nor its slug", session)


@pytest.mark.commands
def test_project_slug_shows_the_summary_and_writes_nothing(sb):
    before = sb.snapshot()

    session = sb.run("/project", "harbor-lights")

    sb.unchanged(before, session)
    sb.expect("Harbor Lights" in session.all_text, "the summary does not name the project", session)


@pytest.mark.commands
def test_project_with_a_duplicated_slug_names_both_notes_and_writes_nothing(sb):
    """`Night Owl` and `Night-Owl` both slugify to `night-owl`. Plan 2.1: with a
    duplicated slug neither resolves (fixture README: "so neither resolves"), so
    the command must not pick one silently. Section 4.1 does not fix the wording;
    asserted: nothing written, and the reply names both notes by title (the
    argument was typed in lower case, so neither title is an echo)."""
    before = sb.snapshot()

    session = sb.run("/project", "night-owl")

    sb.unchanged(before, session)
    text = session.all_text
    sb.expect("Night Owl" in text and "Night-Owl" in text,
              "the reply does not name both notes that share the slug", session)
