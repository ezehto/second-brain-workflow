"""/standup scenario (P1-10, P1-13; plan sections 2.2, 4; SKILL.md command table).

The first scenario's input names work done ("inspected the pier lamps") that
matches the planned task `Inspect the pier lamps`; /standup may offer that
status change but must not make it without asking, so no task note may change.

Plan 4.1 "Ensuring today's note" and "`/standup` details": with no text, a
missing note is still created, exactly as /daily creates it; on a touched note
nothing already there changes and the input is appended under the matching
headings, `- [ ]` under Today and Follow-ups, `- ` elsewhere.

Live: one `claude -p` call per test; three calls.
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


def test_standup_without_text_creates_the_note_as_daily_does(sb):
    """No input: today's note is created with carry-forward, byte for byte the
    new-note expectation of /daily (id the only variable)."""
    folder = sb.CARRY_FORWARD / "new-note"
    spec = json.loads((folder / "scenario.json").read_text(encoding="utf-8"))
    rel = spec["note_path"]
    before, baseline = sb.snapshot(), sb.findings()

    session = sb.run("/standup")

    sb.changes(before, session, added=(rel,))
    sb.expect(sb.sections(rel) == spec["expected_sections"],
              f"sections differ from scenario.json:\n{json.dumps(sb.sections(rel), indent=1)}", session)
    note = sb.note(rel)
    sb.expect(bool(note.note_id) and sb.ID_RE.match(note.note_id) is not None,
              f"id {note.note_id!r} does not match {sb.ID_RE.pattern}", session)
    header = f"---\ntype: daily\nid: {note.note_id}\ncreated: {sb.TODAY}\ntags: []\n---\n".encode()
    expected = header + (folder / spec["files"]["expected_body"]).read_bytes()
    sb.expect(sb.read(rel) == expected,
              f"bytes differ from the /daily new-note expectation:\n{sb.read(rel).decode()}", session)
    printed = [sb.heading_order(block) for block in session.texts]
    sb.expect(list(sb.STANDUP_HEADINGS) in printed,
              f"no message prints all six standup headings in template order: {printed}", session)
    sb.assert_no_new_findings(baseline, session)


TOUCHED_INPUT = (
    "Done: replaced the north jetty fuse. Today: order a spare relay. "
    "Blockers: waiting on the ferry timetable. Decisions: we keep the brass fittings. "
    "Follow-ups: ask the harbour office about parking."
)
# heading -> (distinctive fragment of the input item, appended as a checkbox?)
TOUCHED_ITEMS = {
    "Done": ("north jetty fuse", False),
    "Today": ("spare relay", True),
    "Blockers": ("ferry timetable", False),
    "Decisions / Updates": ("brass fittings", False),
    "Follow-ups": ("harbour office", True),
}


def is_subsequence(needles, haystack):
    it = iter(haystack)
    return all(any(line == needle for line in it) for needle in needles)


def test_standup_appends_input_to_a_touched_note_and_keeps_every_line(sb):
    folder = sb.CARRY_FORWARD / "touched-note"
    spec = json.loads((folder / "scenario.json").read_text(encoding="utf-8"))
    rel = spec["note_path"]
    sb.path(rel).write_bytes((folder / spec["files"]["input"]).read_bytes())
    sb.commit_all("place the touched note")
    before, baseline = sb.snapshot(), sb.findings()
    original_text = sb.read(rel).decode("utf-8")
    original_sections = sb.sections(rel)

    session = sb.run("/standup", TOUCHED_INPUT)

    sb.changes(before, session, changed=(rel,))  # no task changes; a touched note is never refilled
    after_text = sb.read(rel).decode("utf-8")
    sb.expect(is_subsequence(original_text.splitlines(), after_text.splitlines()),
              f"a line that was in the note changed, moved or disappeared:\n{after_text}", session)
    sections = sb.sections(rel)
    for heading, (fragment, checkbox) in TOUCHED_ITEMS.items():
        lines = sections.get(heading, [])
        kept = original_sections.get(heading, [])
        added = lines[len(kept):]
        sb.expect(lines[: len(kept)] == kept, f"{heading}: existing items changed: {lines}", session)
        sb.expect(len(added) == 1 and fragment in added[0].lower(),
                  f"{heading}: expected one appended item containing {fragment!r}, got {added}", session)
        if added:
            prefix_ok = added[0].startswith("- [ ] ") if checkbox else (
                added[0].startswith("- ") and not added[0].startswith("- ["))
            sb.expect(prefix_ok, f"{heading}: {added[0]!r} should be "
                      f"{'a `- [ ]` checkbox' if checkbox else 'a plain `- ` bullet'} (4.1)", session)
    sb.expect(sections.get("Related Tasks / Projects", []) == original_sections.get("Related Tasks / Projects", []),
              "Related Tasks / Projects changed", session)
    printed = [sb.heading_order(block) for block in session.texts]
    sb.expect(list(sb.STANDUP_HEADINGS) in printed,
              f"no message prints all six standup headings in template order: {printed}", session)
    sb.assert_no_new_findings(baseline, session)
