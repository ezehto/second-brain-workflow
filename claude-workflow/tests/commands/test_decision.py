"""/decision scenario (P1-10, P1-11; plan sections 2.5 "Missing folders", 4).

Live: one `claude -p` call. The scenario also covers the missing-folder rule:
`05-Knowledge/Decisions` is a Phase 1 folder, so a command must create it when
it is absent.
"""

import shutil

import pytest

pytestmark = pytest.mark.commands

FOLDER = "05-Knowledge/Decisions"
NEW_DECISION = f"{FOLDER}/Adopt amber lenses for the garden.md"


def test_decision_creates_a_proposed_decision_and_its_missing_phase1_folder(sb):
    shutil.rmtree(sb.path(FOLDER))
    sb.commit_all("remove the decisions folder")
    before, baseline = sb.snapshot(), sb.findings()

    session = sb.run("/decision", "Adopt amber lenses for the garden project:quiet-garden")

    sb.changes(before, session, added=(f"{FOLDER}/", NEW_DECISION))
    note = sb.check_new_note(NEW_DECISION, "decision", session, status="proposed",
                             project="[[Quiet Garden]]", tags=[])
    sb.expect(note.frontmatter.get("decided") is None, "decided is set on a proposed decision", session)
    sb.assert_no_new_findings(baseline, session)
