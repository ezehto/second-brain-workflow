"""A template edited in the vault changes the created note's shape
(P1-10; SKILL.md hard rule 5, plan section 2.9: commands read the vault's templates).

Live: one `claude -p` call.
"""

import pytest

pytestmark = pytest.mark.commands

TEMPLATE = "08-System/Templates/task.md"
NEW_TASK = "02-Work/Tasks/Oil the boathouse hinges.md"


def test_task_follows_the_vault_template_not_the_skill_seed(sb):
    template = sb.read(TEMPLATE).decode()
    edited = template.replace("due:\n", "due:\nestimate:\n", 1).replace(
        "## Notes\n", "## Acceptance criteria\n\n## Notes\n", 1
    )
    assert edited != template and edited.count("estimate:") == 1 and "## Acceptance criteria" in edited
    sb.path(TEMPLATE).write_text(edited)
    sb.commit_all("edit the task template")
    before, baseline = sb.snapshot(), sb.findings()

    session = sb.run("/task", "Oil the boathouse hinges")

    sb.changes(before, session, added=(NEW_TASK,))
    # check_new_note compares keys and headings with the vault's (edited) template.
    note = sb.check_new_note(NEW_TASK, "task", session, status="planned")
    sb.expect("estimate" in note.frontmatter, "the template's new key is missing", session)
    sb.assert_no_new_findings(baseline, session)
