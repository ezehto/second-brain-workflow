"""/daily scenarios: the three golden carry-forward cases (P1-10, P1-13; plan 2.2, 2.4).

Each is compared with fixtures/golden-vault/expected/carry-forward/<case>/ as its
scenario.json says: first the ordered items per section (a readable diff), then
the bytes, which is the comparison scenario.json fixes.

Live: new-note runs /daily twice (two calls; the second run must change
nothing); untouched-note and touched-note one call each.
"""

import json
import shutil

import pytest

pytestmark = pytest.mark.commands


def scenario(sb, case):
    folder = sb.CARRY_FORWARD / case
    return folder, json.loads((folder / "scenario.json").read_text(encoding="utf-8"))


def place_input(sb, folder, spec):
    target = sb.path(spec["note_path"])
    shutil.copyfile(folder / spec["files"]["input"], target)
    sb.commit_all(f"place {spec['scenario']} input")


def test_daily_creates_the_note_with_carry_forward_and_a_rerun_changes_nothing(sb):
    folder, spec = scenario(sb, "new-note")
    rel = spec["note_path"]
    before, baseline = sb.snapshot(), sb.findings()

    first = sb.run("/daily")

    sb.changes(before, first, added=(rel,))
    sb.expect(sb.sections(rel) == spec["expected_sections"],
              f"sections differ from scenario.json:\n{json.dumps(sb.sections(rel), indent=1)}", first)
    note = sb.note(rel)
    sb.expect(bool(note.note_id) and sb.ID_RE.match(note.note_id) is not None,
              f"id {note.note_id!r} does not match {sb.ID_RE.pattern}", first)
    header = f"---\ntype: daily\nid: {note.note_id}\ncreated: {sb.TODAY}\ntags: []\n---\n".encode()
    expected = header + (folder / spec["files"]["expected_body"]).read_bytes()
    sb.expect(sb.read(rel) == expected,
              f"bytes differ from the expected note:\n--- expected\n{expected.decode()}\n--- actual\n"
              f"{sb.read(rel).decode()}", first)
    sb.assert_no_new_findings(baseline, first)

    after_first = sb.snapshot()
    second = sb.run("/daily")
    sb.unchanged(after_first, second)


def test_daily_fills_an_untouched_note_in_place(sb):
    folder, spec = scenario(sb, "untouched-note")
    rel = spec["note_path"]
    place_input(sb, folder, spec)
    before, baseline = sb.snapshot(), sb.findings()

    session = sb.run("/daily")

    sb.changes(before, session, changed=(rel,))
    sb.expect(sb.sections(rel) == spec["expected_sections"],
              f"sections differ from scenario.json:\n{json.dumps(sb.sections(rel), indent=1)}", session)
    expected = (folder / spec["files"]["expected"]).read_bytes()
    sb.expect(sb.read(rel) == expected,
              f"bytes differ from expected.md:\n--- expected\n{expected.decode()}\n--- actual\n"
              f"{sb.read(rel).decode()}", session)
    sb.assert_no_new_findings(baseline, session)


def test_daily_leaves_a_touched_note_unchanged(sb):
    folder, spec = scenario(sb, "touched-note")
    place_input(sb, folder, spec)
    before = sb.snapshot()

    session = sb.run("/daily")

    sb.unchanged(before, session)
    sb.expect(sb.read(spec["note_path"]) == (folder / spec["files"]["input"]).read_bytes(),
              "the touched note changed", session)
