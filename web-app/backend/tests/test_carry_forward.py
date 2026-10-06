"""Carry-forward (plan section 2.2, P1-29): the pure functions and the golden scenarios.

Expectations come from the fixture's `expected/carry-forward/*/scenario.json` and from the
hand-written inputs below, never from the code under test.
"""

import json
from datetime import date

import pytest
from api_support import GOLDEN

from vault import carry_forward, conventions
from vault.carry_forward import carry_items, section_lines, unchecked_items
from vault.models import Note

SCENARIOS = GOLDEN / "expected/carry-forward"
TODAY = date(2026, 10, 9)


def task(path, status, due=None, project=None, **frontmatter):
    return Note(
        path=path,
        title=path.rpartition("/")[2].removesuffix(".md"),
        type="task",
        status=status,
        due=due,
        project=project,
        frontmatter=frontmatter,
    )


def project(path):
    return Note(path=path, title=path.rpartition("/")[2].removesuffix(".md"), type="project")


def items(previous, tasks=(), projects=None, extra_paths=(), today=TODAY):
    paths = (
        [t.path for t in tasks] + [p.path for p in (projects or {}).values()] + list(extra_paths)
    )
    return carry_items(previous, tasks, projects or {}, paths, today)


# --- section and item extraction ----------------------------------------------------------


def test_unchecked_means_a_space_in_the_box_at_any_indent_and_marker():
    body = (
        "## Today\n\n- [ ] a\n  * [ ] b\n+ [ ] c\n- [x] d\n- [X] e\n- [/] f\n- [-] g\n"
        "-[ ] h\n- [ ]i\n1. [ ] j\n"
    )
    assert unchecked_items(body, "Today") == ["- [ ] a", "  * [ ] b", "+ [ ] c"]


def test_section_ends_at_the_next_heading_of_the_same_or_higher_level():
    body = "## Today\n- [ ] a\n### Sub\n- [ ] b\n## Blockers\n- [ ] c\n"
    assert unchecked_items(body, "Today") == ["- [ ] a", "- [ ] b"]
    assert unchecked_items("## Today\n- [ ] a\n# Top\n- [ ] b\n", "Today") == ["- [ ] a"]


def test_heading_matches_by_level_and_case_and_the_first_one_wins():
    body = "# Today\n- [ ] no\n## TODAY ##\n- [ ] yes\n## Today\n- [ ] second\n"
    assert unchecked_items(body, "Today") == ["- [ ] yes"]  # the second `## Today` is not read


def test_fenced_code_holds_neither_headings_nor_items():
    body = "## Today\n- [ ] a\n```\n## Blockers\n- [ ] fenced\n```\n- [ ] b\n## Blockers\n"
    assert unchecked_items(body, "Today") == ["- [ ] a", "- [ ] b"]


def test_a_missing_section_and_crlf_lines():
    assert unchecked_items("## Blockers\n- [ ] a\n", "Today") == []
    assert section_lines("## Today\r\n- [ ] a\r\n", "Today") == ["- [ ] a", ""]


# --- the sections -------------------------------------------------------------------------


def test_every_section_is_present_in_template_order_even_with_nothing_to_carry():
    result = items(None)
    assert list(result) == list(conventions.STANDUP_HEADINGS)
    assert all(lines == [] for lines in result.values())


def test_today_task_items_follow_status_then_due_then_title_then_path():
    tasks = [
        task("02-Work/Tasks/B.md", "planned", date(2026, 10, 1)),
        task("02-Work/Tasks/Z review.md", "review"),
        task("02-Work/Tasks/A review.md", "review"),
        task("02-Work/Tasks/Late.md", "in-progress", date(2026, 10, 8)),
        task("02-Work/Tasks/Early.md", "in-progress", date(2026, 10, 2)),
        task("02-Work/Tasks/None.md", "in-progress"),
        task("02-Work/Tasks/Due today.md", "planned", TODAY),
    ]
    assert items(None, tasks)["Today"] == [
        "- [ ] [[Early]]",
        "- [ ] [[Late]]",
        "- [ ] [[None]]",
        "- [ ] [[A review]]",
        "- [ ] [[Z review]]",
        "- [ ] [[B]]",
        "- [ ] [[Due today]]",
    ]


def test_tasks_that_are_not_carried():
    tasks = [
        task("02-Work/Tasks/Inbox.md", "inbox", date(2026, 10, 1)),
        task("02-Work/Tasks/Done.md", "done", date(2026, 10, 1)),
        task("02-Work/Tasks/Cancelled.md", "cancelled"),
        task("02-Work/Tasks/Future.md", "planned", date(2026, 10, 10)),
        task("02-Work/Tasks/No due.md", "planned"),
        task("02-Work/Tasks/Odd.md", "waiting"),
    ]
    assert items(None, tasks) == items(None)


def test_blockers_carry_the_reason_and_are_ordered_like_task_items():
    tasks = [
        task("02-Work/Tasks/Zed.md", "blocked", None, blocked_by="the  vendor\n"),
        task("02-Work/Tasks/Alpha.md", "blocked", None),
        task("02-Work/Tasks/Dated.md", "blocked", date(2026, 11, 1), blocked_by=3),
        task("02-Work/Tasks/Blank.md", "blocked", date(2026, 10, 30), blocked_by="  "),
        task("02-Work/Tasks/Listed.md", "blocked", date(2026, 12, 1), blocked_by=["a", "b"]),
    ]
    assert items(None, tasks)["Blockers"] == [
        "- [[Blank]]",
        "- [[Dated]] (blocked by: 3)",
        "- [[Listed]]",
        "- [[Alpha]]",
        "- [[Zed]] (blocked by: the vendor)",
    ]


def test_blocked_by_as_an_unquoted_wikilink_is_its_one_item_and_other_lists_are_dropped():
    def reason(value):
        return items(None, [task("02-Work/Tasks/T.md", "blocked", blocked_by=value)])["Blockers"]

    assert reason([["Fix gate"]]) == ["- [[T]] (blocked by: Fix gate)"]
    assert reason(["Fix gate"]) == ["- [[T]] (blocked by: Fix gate)"]
    assert reason([["a"], ["b"]]) == ["- [[T]]"]
    assert reason([["a", "b"]]) == ["- [[T]]"]
    assert reason([]) == ["- [[T]]"]


def test_a_stem_that_is_not_unique_is_linked_with_its_folder():
    tasks = [task("02-Work/Tasks/Plan.md", "review")]
    result = items(None, tasks, extra_paths=["05-Knowledge/Lessons/Plan.md"])
    assert result["Today"] == ["- [ ] [[02-Work/Tasks/Plan]]"]


def test_a_stem_with_a_shell_character_is_always_folder_qualified():
    result = items(None, [task("02-Work/Tasks/Cost $5.md", "review")])
    assert result["Today"] == ["- [ ] [[02-Work/Tasks/Cost $5]]"]


def test_free_text_follows_the_task_items_and_a_task_link_drops_the_item():
    previous = (
        "## Today\n\n- [ ] [[Wire]]\n- [ ] Do [[Wire]] again\n- [ ] Ask [[Nobody]]\n"
        "- [ ] Check the [[Site]]\n- [x] done thing\n"
    )
    tasks = [task("02-Work/Tasks/Wire.md", "in-progress")]
    site = project("02-Work/Projects/Site.md")
    result = items(previous, tasks, {"site": site})
    assert result["Today"] == [
        "- [ ] [[Wire]]",
        "- [ ] Ask [[Nobody]]",
        "- [ ] Check the [[Site]]",
    ]


def test_an_ambiguous_link_that_resolves_to_a_task_drops_the_item():
    previous = "## Today\n- [ ] See [[Plan]]\n"
    tasks = [task("02-Work/Tasks/Plan.md", "inbox")]
    result = items(previous, tasks, extra_paths=["05-Knowledge/Lessons/Plan.md"])
    assert result["Today"] == []


def test_duplicates_go_within_a_section_only_and_whitespace_is_collapsed():
    previous = (
        "## Today\n- [ ] Same  thing\n- [ ] Same thing \n    - [ ] Same thing\n- [ ] Case\n"
        "- [ ] case\n## Follow-ups\n- [ ] Same thing\n- [ ] Same thing\n"
    )
    result = items(previous)
    assert result["Today"] == ["- [ ] Same  thing", "- [ ] Case", "- [ ] case"]
    assert result["Follow-ups"] == ["- [ ] Same thing"]


def test_follow_ups_keep_items_that_link_a_task():
    previous = "## Follow-ups\n- [ ] Call about [[Wire]]\n- [x] sent\n"
    result = items(previous, [task("02-Work/Tasks/Wire.md", "in-progress")])
    assert result["Follow-ups"] == ["- [ ] Call about [[Wire]]"]


def test_related_projects_come_from_today_and_blockers_tasks_only():
    projects = {
        "quiet-garden": project("02-Work/Projects/Quiet Garden.md"),
        "harbor-lights": project("02-Work/Projects/Harbor Lights.md"),
        "idle": project("02-Work/Projects/Idle.md"),
    }
    tasks = [
        task("02-Work/Tasks/One.md", "review", project="quiet-garden"),
        task("02-Work/Tasks/Two.md", "blocked", project="harbor-lights"),
        task("02-Work/Tasks/Three.md", "in-progress", project="quiet-garden"),
        task("02-Work/Tasks/Four.md", "in-progress", project="unknown-slug"),
        task("02-Work/Tasks/Five.md", "inbox", project="idle"),
        task("02-Work/Tasks/Six.md", "in-progress"),
    ]
    previous = "## Today\n- [ ] Visit [[Idle]]\n"
    assert items(previous, tasks, projects)["Related Tasks / Projects"] == [
        "- [[Harbor Lights]]",
        "- [[Quiet Garden]]",
    ]


# --- against the golden vault -------------------------------------------------------------


def test_previous_daily_is_the_latest_strictly_before_today():
    paths = [
        "01-Daily/2026/2026-10-05.md",
        "01-Daily/2026/2026-10-07.md",
        "01-Daily/2026/2026-10-09.md",
        "01-Daily/2026/2026-10-11.md",
        "01-Daily/2026/notes.md",
        "01-Daily/2026/2026-13-01.md",
        "02-Work/2026-10-08.md",
    ]
    previous = carry_forward._previous_daily_path
    assert previous(paths, date(2026, 10, 9)) == "01-Daily/2026/2026-10-07.md"
    assert previous(paths, date(2026, 10, 7)) == "01-Daily/2026/2026-10-05.md"
    assert previous(paths, date(2026, 10, 5)) is None


@pytest.mark.django_db
def test_preview_reads_the_previous_note_found_by_date(golden_index):
    assert carry_forward.preview(date(2026, 10, 9))["Follow-ups"]  # from 2026-10-07
    assert carry_forward.preview(date(2026, 10, 7))["Follow-ups"] == [  # from 2026-10-05
        "- [ ] Ask about the older lamp stock"
    ]
    assert carry_forward.preview(date(2026, 10, 5))["Follow-ups"] == []  # no earlier note


@pytest.mark.django_db
@pytest.mark.parametrize("scenario", ["new-note", "untouched-note"])
def test_preview_equals_the_golden_expected_sections(golden_index, scenario):
    expected = json.loads((SCENARIOS / scenario / "scenario.json").read_text())
    assert carry_forward.preview(TODAY) == expected["expected_sections"]
    assert list(carry_forward.preview(TODAY)) == list(conventions.STANDUP_HEADINGS)


@pytest.mark.django_db
def test_preview_with_no_previous_note_still_carries_tasks(golden_index):
    result = carry_forward.preview(date(2026, 10, 5))
    assert result["Follow-ups"] == []
    assert result["Blockers"] == [
        "- [[Fix gate latch]] (blocked by: Waiting for hinge delivery)",
        "- [[Replace fence post]]",
    ]
