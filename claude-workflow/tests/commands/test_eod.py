"""/eod scenarios (P1-10, P1-14; plan sections 2.6, 4, 4.1, 4.2).

Setup for every test: today's daily note (the fixture's touched note, which has a
`## Done` section and one typed Today item) is placed and committed as
`eod: 2026-10-08`, yesterday's end-of-day commit. A first /eod today must add a
new commit on top of it; only a second run the same day amends (4.2).

The scenarios run under the `eod` permission profile, whose only git surface is
`python3 -I <work>/.claude/skills/second-brain/scripts/vault_git.py <verb>`, and
they are the only scenarios allowed to move HEAD or the index.

The fixture has three `in-progress` tasks, so turn 1 always lists them and asks
(4.1 step 4); the commit can only come in turn 2.

`vault_git.py` behaviour these scenarios rely on (plan 4.2): `commit-eod` stages
every change itself; "nothing to commit" is an outcome with exit code 0, which no
scenario here reaches (each one leaves a change to commit); a secret refusal
commits nothing, leaves the changes staged and lists `<file>:<line> (<kind>)`
entries, so the scenario asserts the file name appears and the value does not.
The wrapper's allow rules are exact strings: a call with `2>&1` or `; echo $?`
appended is denied, and the failure output lists each denied command in full.

Live calls: no-status-change 2, yes 2, amend 2, secret 2, remote 1.
"""

import pytest

pytestmark = pytest.mark.commands

WIRE = "02-Work/Tasks/Wire the dock lights.md"
IN_PROGRESS_TITLES = ("Wire the dock lights", "Release checklist", "Calibrate light sensor")
IGNORED_IN_PROGRESS = ("Ignored by sbignore", "Scratch pad")  # in-progress but ignored (.sbignore)
YESTERDAY_SUBJECT = "eod: 2026-10-08"
SUBJECT = "eod: 2026-10-09"
DONE_TEXT = "Checked the lantern stands on the east pier"
EVIDENCE = "all six dock lights were tested after dark and work"
EVIDENCE_FRAGMENT = "tested after dark"
NO = "No, leave every task status as it is."
SECRET_NOTE = "00-Inbox/2026-10-09 1650 Router settings for the shed.md"
SECRET_VALUE = "hunter2-lantern-42"


@pytest.fixture
def eod(sb):
    source = sb.CARRY_FORWARD / "touched-note" / "input.md"
    sb.path(sb.DAILY_NOTE).write_bytes(source.read_bytes())
    sb.commit_all(YESTERDAY_SUBJECT)
    sb.profile = "eod"
    sb.allow_git_writes = True
    return sb


def subjects(sb):
    return sb.git("log", "--format=%s").splitlines()


def expect_new_eod_commit(sb, session, parent):
    """HEAD is today's eod commit, directly on `parent`, and nothing is left uncommitted."""
    sb.expect(subjects(sb)[0] == SUBJECT, f"HEAD subject is {subjects(sb)[0]!r}, expected {SUBJECT!r}", session)
    sb.expect(sb.git("rev-parse", "HEAD^").strip() == parent,
              f"the eod commit's parent is not {parent} (log: {subjects(sb)})", session)
    sb.expect(subjects(sb).count(SUBJECT) == 1, f"more than one eod commit today: {subjects(sb)}", session)
    status = sb.git("status", "--porcelain")
    sb.expect(status.strip() == "", f"uncommitted changes remain after /eod:\n{status}", session)
    sb.expect(sb.git("remote").strip() == "", "a remote was added", session)


def expect_turn1_offers_status_changes(sb, session, before, start):
    """Turn 1 may append to today's ## Done; it lists the in-progress tasks and
    asks; nothing else is written and nothing is committed yet."""
    sb.changes(before, session, optional_changed=(sb.DAILY_NOTE,))
    sb.expect(sb.head() == start, "/eod committed before the status-change question was answered", session)
    text = session.all_text
    missing = [t for t in IN_PROGRESS_TITLES if t not in text]
    sb.expect(not missing, f"turn 1 does not offer status changes for {missing}", session)
    listed = [t for t in IGNORED_IN_PROGRESS if t in text]
    sb.expect(not listed, f"turn 1 offers ignored notes: {listed}", session)


def expect_only_done_changed(sb, session, before_bytes):
    """4.1 step 3: the text is appended to ## Done and every other section is unchanged."""
    from_text = before_bytes.decode("utf-8")
    sections = sb.sections(sb.DAILY_NOTE)
    done = sections.pop("Done", [])
    sb.expect(any(DONE_TEXT.lower() in line.lower() for line in done), f"the text is not under ## Done: {done}", session)
    original = sb.sections_of(from_text)
    original.pop("Done", None)
    sb.expect(sections == original, f"sections other than ## Done changed:\n{sections}\nvs\n{original}", session)


def test_eod_appends_done_commits_once_and_changes_no_status_without_yes(eod):
    sb = eod
    before, start, baseline = sb.snapshot(), sb.head(), sb.findings()
    daily_before = sb.read(sb.DAILY_NOTE)

    turn1 = sb.run("/eod", DONE_TEXT)
    expect_turn1_offers_status_changes(sb, turn1, before, start)
    turn2 = sb.reply(turn1, NO)

    sb.changes(before, turn2, changed=(sb.DAILY_NOTE,))
    expect_only_done_changed(sb, turn2, daily_before)
    expect_new_eod_commit(sb, turn2, start)
    sb.assert_no_new_findings(baseline, turn2)


def test_eod_applies_a_status_change_on_yes_and_commits_it(eod):
    sb = eod
    before, start, baseline = sb.snapshot(), sb.head(), sb.findings()
    daily_before = sb.read(sb.DAILY_NOTE)

    turn1 = sb.run("/eod", DONE_TEXT)
    expect_turn1_offers_status_changes(sb, turn1, before, start)
    turn2 = sb.reply(
        turn1,
        f"Yes: mark Wire the dock lights as done. Evidence: {EVIDENCE}. Leave every other task unchanged.",
    )

    sb.changes(before, turn2, changed=(sb.DAILY_NOTE, WIRE))
    expect_only_done_changed(sb, turn2, daily_before)
    wire = sb.note(WIRE)
    sb.expect(wire.status == "done", f"{WIRE}: status is {wire.status!r}", turn2)
    notes = sb.sections(WIRE).get("Notes", [])
    sb.expect(any(EVIDENCE_FRAGMENT in line.lower() for line in notes), f"evidence not under ## Notes: {notes}", turn2)
    expect_new_eod_commit(sb, turn2, start)
    sb.assert_no_new_findings(baseline, turn2)


def test_eod_amends_todays_eod_commit_on_a_second_run(eod):
    """A first run today is simulated by committing `eod: 2026-10-09` on top of
    yesterday's; a new capture is then left uncommitted. The second run must
    amend: still exactly one commit for today, on yesterday's."""
    sb = eod
    yesterday = sb.head()
    first = sb.commit_all(SUBJECT)
    capture = "00-Inbox/2026-10-09 1700 Ask about lantern stands.md"
    sb.path(capture).write_text(
        "---\ntype: capture\nid: 20261009170000\nstatus: inbox\ncreated: 2026-10-09\ntags: []\n---\n\n"
        "Ask about lantern stands\n"
    )
    before = sb.snapshot()

    turn1 = sb.run("/eod", DONE_TEXT)
    expect_turn1_offers_status_changes(sb, turn1, before, first)
    turn2 = sb.reply(turn1, NO)

    expect_new_eod_commit(sb, turn2, yesterday)
    sb.expect(sb.head() != first, "HEAD is unchanged: the second run did not amend", turn2)
    tree = sb.git("ls-tree", "-r", "--name-only", "HEAD").splitlines()
    sb.expect(capture in tree, "the new capture is not in the amended commit", turn2)


def test_eod_stops_on_a_planted_secret_and_names_the_file(eod):
    sb = eod
    # The body does not repeat the file name, so naming the file is a real check.
    sb.path(SECRET_NOTE).write_text(
        "---\ntype: capture\nid: 20261009165000\nstatus: inbox\ncreated: 2026-10-09\ntags: []\n---\n\n"
        f"Shed access point login\n\npassword: {SECRET_VALUE}\n"
    )
    start = sb.head()

    turn1 = sb.run("/eod", DONE_TEXT)
    turn2 = sb.reply(turn1, NO)

    sb.expect(sb.head() == start, "/eod committed despite the planted secret", turn2)
    said = turn1.all_text + "\n" + turn2.all_text
    sb.expect("Router settings for the shed" in said, "the secret-scan stop does not name the file", turn2)
    sb.expect(SECRET_VALUE not in said, "a reply repeats the secret's value", turn2)


def test_eod_refuses_to_run_when_the_vault_has_a_remote(eod):
    sb = eod
    sb.git("remote", "add", "origin", str(sb.ws.root / "no-such-remote.git"))
    before, start = sb.snapshot(), sb.head()

    session = sb.run("/eod", DONE_TEXT)

    sb.unchanged(before, session)  # 4.1 step 1: refuse before writing anything
    sb.expect(sb.head() == start, "/eod committed with a remote configured", session)
    sb.expect(sb.git("remote").split() == ["origin"], "the remote configuration changed", session)
    sb.expect("remote" in session.all_text.lower(), "the refusal does not mention the remote", session)
