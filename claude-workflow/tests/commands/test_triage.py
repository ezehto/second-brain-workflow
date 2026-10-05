"""/triage two-turn scenarios (P1-10, P1-12; plan sections 2.13, 4, 4.1; reference/triage.md).

The fixture has three inbox captures (fixture README):

- HINGE "Buy a spare hinge for the gate": a plain imperative, high
  confidence: turn 1 writes `classification: task`.
- FLICKER "Why do the garden lights flicker after rain? ...": a question,
  high confidence under plan 4.1: turn 1 writes `classification: question`.
  It has no Phase 1 target and stays in the inbox.
- LANTERNS "Maybe the lanterns could change colour at dusk ...": low
  confidence: nothing written in turn 1, only a suggestion.

The "yes" answer dismisses LANTERNS, so the outcome is fixed: HINGE becomes the
task `Buy a spare hinge for the gate` (the capture text sanitised, 4.1), written
before HINGE is marked triaged; LANTERNS is dismissed; FLICKER is untouched.
"No" changes nothing beyond turn 1's classifications (4.1).

The later scenarios (plan 4.1 "`/triage` details") pin every capture's final kind
in the turn-2 answer, because a low-confidence suggestion is not deterministic:
a re-classified high-confidence capture, a low-confidence capture converted as
a kind with a target, and the two no-target outcomes (kept with its
classification, or dismissed).

Live: two `claude -p` calls per test; ten calls.
"""

import pytest

pytestmark = pytest.mark.commands

HINGE = "00-Inbox/2026-10-08 0915 Buy a spare hinge for the gate.md"
LANTERNS = "00-Inbox/2026-10-08 1240 Maybe the lanterns could change colour at dusk.md"
FLICKER = "00-Inbox/2026-10-08 1605 Why do the garden lights flicker after rain.md"
TARGET = "02-Work/Tasks/Buy a spare hinge for the gate.md"
CLASSIFICATIONS = {"task", "problem", "decision", "learning-topic", "note", "project",
                   "ticket", "architecture-idea", "question", "thought"}
WRITE_TOOLS = {"Write", "Edit"}

YES = "Yes, apply the batch, with one change: dismiss the capture about the lanterns changing colour at dusk."
NO = "No. Do not create or change anything."


def expect_capture(sb, session, original, rel, optional=(), **values):
    """The capture's frontmatter has `values`; keys in `optional` may be added
    with an allowed classification; every other key and the body are unchanged."""
    note = sb.note(rel)
    for key, value in values.items():
        sb.expect(note.frontmatter.get(key) == value,
                  f"{rel}: {key} is {note.frontmatter.get(key)!r}, expected {value!r}", session)
    for key in optional:
        if key in note.frontmatter and key not in original.frontmatter:
            sb.expect(note.frontmatter[key] in CLASSIFICATIONS,
                      f"{rel}: {key} {note.frontmatter[key]!r} is not an allowed value", session)
    skip = set(values) | set(optional)
    others = {k: v for k, v in note.frontmatter.items() if k not in skip}
    original_others = {k: v for k, v in original.frontmatter.items() if k not in skip}
    sb.expect(others == original_others, f"{rel}: other frontmatter changed: {others} vs {original_others}", session)
    sb.expect(note.body == original.body, f"{rel}: body changed", session)


def run_turn1(sb):
    """Turn 1 and its assertions, shared by both tests."""
    before, baseline = sb.snapshot(), sb.findings()
    originals = {rel: sb.note(rel) for rel in (HINGE, LANTERNS, FLICKER)}

    turn1 = sb.run("/triage")

    sb.changes(before, turn1, changed=(HINGE, FLICKER))
    expect_capture(sb, turn1, originals[HINGE], HINGE, classification="task", status="inbox")
    expect_capture(sb, turn1, originals[FLICKER], FLICKER, classification="question", status="inbox")
    for word in ("hinge", "lantern", "flicker"):
        sb.expect(word in turn1.all_text.lower(), f"the batch listing does not mention the {word!r} capture", turn1)
    sb.assert_no_new_findings(baseline, turn1)
    return turn1, before, originals, baseline


def test_triage_yes_creates_the_target_first_then_marks_the_captures(sb):
    turn1, before, originals, baseline = run_turn1(sb)
    after_turn1 = sb.snapshot()

    turn2 = sb.reply(turn1, YES)

    sb.changes(before, turn2, added=(TARGET,), changed=(HINGE, LANTERNS, FLICKER))
    sb.changes(after_turn1, turn2, added=(TARGET,), changed=(HINGE, LANTERNS))  # FLICKER untouched in turn 2
    sb.check_new_note(TARGET, "task", turn2)
    expect_capture(sb, turn2, originals[HINGE], HINGE, classification="task", status="triaged",
                   triaged_to=sb.emitted_link(TARGET))
    expect_capture(sb, turn2, originals[LANTERNS], LANTERNS, status="dismissed")
    expect_capture(sb, turn2, originals[FLICKER], FLICKER, classification="question", status="inbox")

    writes = [args.get("file_path", "") for name, args in turn2.tool_uses if name in WRITE_TOOLS]
    target_at = next((i for i, p in enumerate(writes) if p == str(sb.path(TARGET))), None)
    hinge_at = next((i for i, p in enumerate(writes) if p == str(sb.path(HINGE))), None)
    sb.expect(target_at is not None and hinge_at is not None and target_at < hinge_at,
              f"the target note was not written before the capture was marked (writes: {writes})", turn2)
    sb.assert_no_new_findings(baseline, turn2)


def expect_target_before_capture(sb, session, target, capture):
    """The target note is written before its capture is edited (tool-use order)."""
    writes = [args.get("file_path", "") for name, args in session.tool_uses if name in WRITE_TOOLS]
    target_at = next((i for i, p in enumerate(writes) if p == str(sb.path(target))), None)
    capture_at = next((i for i, p in enumerate(writes) if p == str(sb.path(capture))), None)
    sb.expect(target_at is not None and capture_at is not None and target_at < capture_at,
              f"{target} was not written before {capture} was marked (writes: {writes})", session)


def test_triage_no_creates_nothing(sb):
    turn1, _, _, _ = run_turn1(sb)
    after_turn1 = sb.snapshot()

    turn2 = sb.reply(turn1, NO)

    sb.unchanged(after_turn1, turn2)


def test_triage_yes_with_a_reclassified_capture_creates_the_new_kind(sb):
    """The user turns HINGE (written `task` in turn 1) into a decision: the target
    is a decision note, and the capture's final classification is `decision`."""
    decision = "05-Knowledge/Decisions/Buy a spare hinge for the gate.md"
    turn1, before, originals, baseline = run_turn1(sb)
    after_turn1 = sb.snapshot()

    turn2 = sb.reply(turn1, "Yes, apply the batch with two changes: treat the capture about the spare hinge "
                            "for the gate as a decision, not a task; and dismiss the capture about the lanterns "
                            "changing colour at dusk.")

    sb.changes(after_turn1, turn2, added=(decision,), changed=(HINGE, LANTERNS), optional_changed=(FLICKER,))
    sb.check_new_note(decision, "decision", turn2)
    expect_capture(sb, turn2, originals[HINGE], HINGE, classification="decision", status="triaged",
                   triaged_to=sb.emitted_link(decision))
    expect_capture(sb, turn2, originals[LANTERNS], LANTERNS, status="dismissed")
    expect_capture(sb, turn2, originals[FLICKER], FLICKER, classification="question", status="inbox")
    expect_target_before_capture(sb, turn2, decision, HINGE)
    sb.assert_no_new_findings(baseline, turn2)


def test_triage_yes_converts_a_low_confidence_capture_given_a_kind_with_a_target(sb):
    """LANTERNS (low confidence, nothing written in turn 1) is accepted as a
    learning-topic: a lesson titled with the sanitised capture text (4.1)."""
    lesson = "05-Knowledge/Lessons/Maybe the lanterns could change colour at dusk slowly like the old ones did.md"
    turn1, before, originals, baseline = run_turn1(sb)
    after_turn1 = sb.snapshot()

    turn2 = sb.reply(turn1, "Yes, apply the batch, and convert the capture about the lanterns changing colour "
                            "at dusk as a learning-topic.")

    sb.changes(after_turn1, turn2, added=(TARGET, lesson), changed=(HINGE, LANTERNS), optional_changed=(FLICKER,))
    sb.check_new_note(TARGET, "task", turn2)
    sb.check_new_note(lesson, "lesson", turn2)
    expect_capture(sb, turn2, originals[HINGE], HINGE, classification="task", status="triaged",
                   triaged_to=sb.emitted_link(TARGET))
    expect_capture(sb, turn2, originals[LANTERNS], LANTERNS, classification="learning-topic", status="triaged",
                   triaged_to=sb.emitted_link(lesson))
    expect_capture(sb, turn2, originals[FLICKER], FLICKER, classification="question", status="inbox")
    expect_target_before_capture(sb, turn2, TARGET, HINGE)
    expect_target_before_capture(sb, turn2, lesson, LANTERNS)
    sb.assert_no_new_findings(baseline, turn2)


def test_triage_no_target_kinds_are_kept_with_their_classification_or_dismissed(sb):
    """(a) LANTERNS, low confidence, is accepted as a thought: no Phase 1 target,
    so it keeps `status: inbox` and gains `classification: thought`. (b) FLICKER,
    a question (no target), is dismissed: `status: dismissed` whatever its kind."""
    turn1, before, originals, baseline = run_turn1(sb)
    after_turn1 = sb.snapshot()

    turn2 = sb.reply(turn1, "Yes, apply the batch with two changes: treat the capture about the lanterns "
                            "changing colour at dusk as a thought and keep it; and dismiss the question about "
                            "the garden lights flickering after rain.")

    sb.changes(after_turn1, turn2, added=(TARGET,), changed=(HINGE, LANTERNS, FLICKER))
    sb.check_new_note(TARGET, "task", turn2)
    expect_capture(sb, turn2, originals[HINGE], HINGE, classification="task", status="triaged",
                   triaged_to=sb.emitted_link(TARGET))
    expect_capture(sb, turn2, originals[LANTERNS], LANTERNS, classification="thought", status="inbox")
    expect_capture(sb, turn2, originals[FLICKER], FLICKER, classification="question", status="dismissed")
    expect_target_before_capture(sb, turn2, TARGET, HINGE)
    sb.assert_no_new_findings(baseline, turn2)
