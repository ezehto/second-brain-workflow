"""/knowledge scenario (P1-10, P1-11; plan sections 2.5 "Emitted links", 4).

Live: one `claude -p` call. `Lantern Festival` is the stem of both a project and
a decision in the fixture, so the `project` link must be folder-qualified.
"""

import pytest

pytestmark = pytest.mark.commands

NEW_LESSON = "05-Knowledge/Lessons/Hang festival lanterns higher.md"


def test_knowledge_creates_a_lesson_with_a_folder_qualified_project_link(sb):
    before, baseline = sb.snapshot(), sb.findings()

    session = sb.run("/knowledge", "Hang festival lanterns higher project:lantern-festival")

    sb.changes(before, session, added=(NEW_LESSON,))
    sb.check_new_note(NEW_LESSON, "lesson", session, status="active",
                      project="[[02-Work/Projects/Lantern Festival]]", tags=[])
    sb.assert_no_new_findings(baseline, session)
