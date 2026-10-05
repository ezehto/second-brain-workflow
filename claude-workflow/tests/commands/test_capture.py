"""/capture scenarios (P1-10, P1-11; plan sections 2.5 rule 9, 2.12, 4).

Live: each test runs `claude -p` once (see conftest.py); two calls.
"""

import re

import pytest

pytestmark = pytest.mark.commands

TEXT = "Order more lamp oil before the festival weekend begins soon"
# 2.5 rule 9: `YYYY-MM-DD HHmm <first 8 words of the text>`, date pinned by the test clock.
CAPTURE_NAME = re.compile(r"00-Inbox/2026-10-09 ([0-9]{4}) Order more lamp oil before the festival weekend\.md")


def test_capture_writes_one_inbox_note_named_from_the_first_eight_words(sb):
    before, baseline = sb.snapshot(), sb.findings()

    session = sb.run("/capture", TEXT)

    rel = sb.changes(before, session, added=(CAPTURE_NAME,))[CAPTURE_NAME]
    note = sb.check_new_note(rel, "capture", session, status="inbox", tags=[])
    hhmm = CAPTURE_NAME.fullmatch(rel).group(1)
    sb.expect(note.note_id[8:12] == hhmm,
              f"the id's time {note.note_id[8:12]} differs from the name's {hhmm}: one clock read (2.12)", session)
    sb.expect(TEXT in note.body, f"the capture body does not hold the full text: {note.body!r}", session)
    sb.assert_no_new_findings(baseline, session)


UNSAFE_TEXT = "Why is the pier lamp: flickering? Check the relay tonight please"
# Plan 2.5, by hand: rule 9 takes the first 8 words, "Why is the pier lamp:
# flickering? Check the"; rule 3 replaces `:` and `?` with a space, giving
# "Why is the pier lamp  flickering  Check the"; rule 4 collapses the runs of
# spaces; rule 5 finds no leading dot and no trailing dot or space. The name is
# "2026-10-09 HHmm Why is the pier lamp flickering Check the.md".
UNSAFE_NAME = re.compile(r"00-Inbox/2026-10-09 ([0-9]{4}) Why is the pier lamp flickering Check the\.md")


def test_capture_sanitises_colon_and_question_mark_in_the_name_and_keeps_the_body(sb):
    before, baseline = sb.snapshot(), sb.findings()

    session = sb.run("/capture", UNSAFE_TEXT)

    rel = sb.changes(before, session, added=(UNSAFE_NAME,))[UNSAFE_NAME]
    note = sb.check_new_note(rel, "capture", session, status="inbox", tags=[])
    sb.expect(UNSAFE_TEXT in note.body, f"the body is not the text verbatim: {note.body!r}", session)
    sb.assert_no_new_findings(baseline, session)
