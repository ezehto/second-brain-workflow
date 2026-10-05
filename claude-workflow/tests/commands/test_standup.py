"""/standup scenario (P1-10, P1-13; plan sections 2.2, 4; SKILL.md command table).

Live: one `claude -p` call. The input names work done ("inspected the pier
lamps") that matches the planned task `Inspect the pier lamps`; /standup may
offer that status change but must not make it without asking, so no task note
may change.
"""

import json

import pytest

pytestmark = pytest.mark.commands

INPUT = "Done: inspected the pier lamps at the north jetty. Decisions: we will keep the warm white bulbs."


def test_standup_ensures_the_daily_note_fills_sections_and_prints_six_headings(sb):
    spec = json.loads((sb.CARRY_FORWARD / "new-note" / "scenario.json").read_text(encoding="utf-8"))
    rel = sb.DAILY_NOTE
    before, baseline = sb.snapshot(), sb.findings()

    session = sb.run("/standup", INPUT)

    sb.changes(before, session, added=(rel,))  # no task note changes: a status change needs asking
    sections = sb.sections(rel)
    sb.expect(list(sections) == list(sb.STANDUP_HEADINGS), f"note headings are {list(sections)}", session)
    sb.expect(any("north jetty" in line for line in sections["Done"]),
              f"the input's done item is not under Done: {sections['Done']}", session)
    sb.expect(any("warm white" in line for line in sections["Decisions / Updates"]),
              f"the input's decision is not under Decisions / Updates: {sections['Decisions / Updates']}", session)
    # The carried-forward items must still be there, unchecked: plan 4.1 says
    # /standup never ticks or removes a carried-forward item.
    for name in ("Today", "Blockers", "Follow-ups"):
        missing = [item for item in spec["expected_sections"][name] if item not in sections[name]]
        sb.expect(not missing, f"carry-forward items missing from {name}: {missing}", session)
    # 4.1: the standup text is printed in the same turn, before any question.
    printed = [sb.heading_order(block) for block in session.texts]
    sb.expect(list(sb.STANDUP_HEADINGS) in printed,
              f"no message prints all six standup headings in template order: {printed}", session)
    sb.assert_no_new_findings(baseline, session)
