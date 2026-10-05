"""/task scenarios (P1-10, P1-11; plan sections 2.1, 2.3, 2.5, 4; SKILL.md dates rule).

Live: one `claude -p` call per test, two for the two-turn `done` tests; twelve calls.
"""

import re
from datetime import date

import pytest

pytestmark = pytest.mark.commands

NEW_TASK = "02-Work/Tasks/Replace the harbor lamp lenses.md"
PAINT = "02-Work/Tasks/Paint the gate.md"  # planned, due 2026-10-20
WIRE = "02-Work/Tasks/Wire the dock lights.md"  # in-progress
EVIDENCE = "all six dock lights were tested after dark and work"
EVIDENCE_FRAGMENT = "tested after dark"  # matched case-insensitively
RESOLVED_DUE = re.compile(r"2026-10-16|16 October|October 16")


def test_task_creates_a_planned_task_with_project_link_and_resolved_due(sb):
    """`friday` is the next Friday strictly after today; 2026-10-09 is a Friday."""
    before, baseline = sb.snapshot(), sb.findings()

    session = sb.run("/task", "Replace the harbor lamp lenses project:harbor-lights due:friday priority:high")

    sb.changes(before, session, added=(NEW_TASK,))
    sb.check_new_note(NEW_TASK, "task", session, status="planned", priority="high",
                      project="[[Harbor Lights]]", due=date(2026, 10, 16), tags=[])
    sb.expect(RESOLVED_DUE.search(session.all_text) is not None,
              "the reply does not report the resolved due date 2026-10-16 (4.1)", session)
    sb.assert_no_new_findings(baseline, session)


def test_task_with_an_unknown_project_writes_nothing_and_lists_known_projects(sb):
    before = sb.snapshot()

    session = sb.run("/task", "Polish the brass bell project:lighthouse-tour")

    sb.unchanged(before, session)
    known = ("Harbor Lights", "Quiet Garden", "Lantern Festival")
    sb.expect(any(name in session.all_text for name in known),
              f"the reply lists none of the known projects {known}", session)


def test_task_status_change_rewrites_only_the_status_line(sb):
    before = sb.snapshot()
    original = sb.read(PAINT)

    session = sb.run("/task", "Paint the gate status:in-progress")

    sb.changes(before, session, changed=(PAINT,))
    expected = original.replace(b"\nstatus: planned\n", b"\nstatus: in-progress\n", 1)
    sb.expect(sb.read(PAINT) == expected,
              f"{PAINT} changed beyond its status line:\n{sb.read(PAINT).decode()}", session)


def test_task_done_asks_for_evidence_then_records_it_on_yes(sb):
    before, baseline = sb.snapshot(), sb.findings()
    original = sb.note(WIRE)

    turn1 = sb.run("/task", "Wire the dock lights status:done")
    sb.unchanged(before, turn1)  # nothing is written before the answer
    sb.expect("evidence" in turn1.all_text.lower(), "turn 1 does not ask for evidence (4.1)", turn1)

    turn2 = sb.reply(turn1, f"Yes, mark it done. Evidence: {EVIDENCE}.")

    sb.changes(before, turn2, changed=(WIRE,))
    note = sb.note(WIRE)
    sb.expect(note.status == "done", f"status is {note.status!r}, expected 'done'", turn2)
    sb.expect({k: v for k, v in note.frontmatter.items() if k != "status"}
              == {k: v for k, v in original.frontmatter.items() if k != "status"},
              "frontmatter keys other than status changed", turn2)
    # Plan 4.1: the evidence is appended first and the status line changed
    # second (one edit carrying both is also fine), so a stop in between never
    # leaves a `done` task without evidence.
    evidence_at = sb.first_write_containing(turn2, WIRE, EVIDENCE_FRAGMENT)
    status_at = sb.first_write_containing(turn2, WIRE, "status: done")
    sb.expect(evidence_at is not None and status_at is not None and evidence_at <= status_at,
              f"the evidence was not written before the status (writes: {sb.file_writes(turn2, WIRE)})", turn2)
    sections = sb.sections(WIRE)
    sb.expect(any(EVIDENCE_FRAGMENT in line.lower() for line in sections.get("Notes", [])),
              f"the evidence is not under ## Notes: {sections}", turn2)
    sb.expect(sections.get("Description") == ["Wire the dock lights."], "## Description changed", turn2)
    sb.assert_no_new_findings(baseline, turn2)


def test_task_done_changes_nothing_on_no(sb):
    before = sb.snapshot()

    turn1 = sb.run("/task", "Wire the dock lights status:done")
    sb.unchanged(before, turn1)
    turn2 = sb.reply(turn1, "No, do not mark it done.")

    sb.unchanged(before, turn2)


def test_task_refuses_to_change_a_template(sb):
    """Plan 4.1 "Changing an existing note": a path the user gives is accepted only
    if `stem` prints it as a `note` line; a template is only ever an `ignored`
    line (4.2), so this is refused."""
    template = "08-System/Templates/task.md"
    before = sb.snapshot()
    original = sb.read(template)

    session = sb.run("/task", f"{template} status:in-progress")

    sb.unchanged(before, session)
    sb.expect(sb.read(template) == original, "the template changed", session)


def test_task_with_an_existing_title_writes_nothing_and_asks_for_another(sb):
    """`02-Work/Tasks/Paint the gate.md` exists in the fixture: a same-folder name
    clash (2.5) is refused and the command asks for a different title."""
    assert sb.path(PAINT).is_file()
    before = sb.snapshot()

    session = sb.run("/task", "Paint the gate")

    sb.unchanged(before, session)
    text = session.all_text.lower()
    sb.expect("title" in text and ("exist" in text or "already" in text),
              "the reply does not say the title exists and ask for another", session)


def test_task_named_like_an_ignored_note_writes_nothing_and_asks_for_another(sb):
    """`02-Work/Tasks/Scratch pad.md` is ignored by the fixture's `.sbignore`, so
    `stem` reports it as an `ignored` line, not a note; the file still occupies
    the name in the folder (2.5 clash check reads the filesystem). Asserted:
    nothing written or overwritten, the file byte-identical, and the command
    asks for a different title."""
    scratch = "02-Work/Tasks/Scratch pad.md"
    assert sb.path(scratch).is_file()
    before = sb.snapshot()
    original = sb.read(scratch)

    session = sb.run("/task", "Scratch pad")

    sb.unchanged(before, session)
    sb.expect(sb.read(scratch) == original, f"{scratch} changed", session)
    sb.expect("title" in session.all_text.lower(), "the reply does not ask for a different title", session)


def test_task_title_with_a_dollar_sign_gets_a_safe_file_name(sb):
    """Plan 2.5 rule 3 replaces `$` with a space, rule 4 collapses the run:
    "Pay $5 invoice" becomes `Pay 5 invoice.md`. The title is the file name stem;
    the task template has no title heading, so the body is the template's
    headings (section 3). No Bash call may contain `$` (plan 4.1)."""
    new_task = "02-Work/Tasks/Pay 5 invoice.md"
    before, baseline = sb.snapshot(), sb.findings()

    session = sb.run("/task", "Pay $5 invoice")

    sb.changes(before, session, added=(new_task,))
    sb.check_new_note(new_task, "task", session, status="planned")
    with_dollar = [args.get("command", "") for name, args in session.tool_uses
                   if name == "Bash" and "$" in args.get("command", "")]
    sb.expect(not with_dollar, f"Bash calls contained `$`: {with_dollar}", session)
    sb.assert_no_new_findings(baseline, session)


def test_task_refuses_to_change_a_note_with_malformed_frontmatter(sb):
    """Plan 4.1 "Changing an existing note": a note whose frontmatter is malformed
    is never edited; the command says so and stops. `Broken yaml task.md` has an
    unclosed flow sequence (fixture README)."""
    broken = "02-Work/Tasks/Broken yaml task.md"
    before = sb.snapshot()
    original = sb.read(broken)

    session = sb.run("/task", "Broken yaml task status:in-progress")

    sb.unchanged(before, session)
    sb.expect(sb.read(broken) == original, f"{broken} changed", session)
    sb.expect("frontmatter" in session.text.lower(), "the reply does not say the frontmatter is the problem", session)
