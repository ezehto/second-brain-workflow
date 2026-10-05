"""Test-mode guard (P1-10; plan section 2.12; SKILL.md "Vault path and today's date").

With SECOND_BRAIN_TEST_MODE=1 and SECOND_BRAIN_TODAY set but SECOND_BRAIN_VAULT
unset, a command must refuse and write nothing. Without the variable the
skill's default vault is the real one, so the scenario runs under the `guard`
permission profile, which holds even if `/mnt/d/Second Brain` exists:

- no file-writing tool is offered (Read, Bash, Skill only);
- Bash is limited to the exact printenv, date, `[` and `test` forms of the skill
  and `echo`; no git surface, no listing; command and process substitution
  are denied;
- Read and Edit are denied on the real vault, the old vault, ~/.claude and this
  repository, and Edit deny rules also cover Bash redirections;
- the harness refuses to launch unless the working directory and --add-dir are
  under the test's temporary root.

Live: one `claude -p` call.
"""

import json

import pytest

pytestmark = pytest.mark.commands

WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}


def test_command_refuses_in_test_mode_without_a_vault_path(sb, hx):
    real_vault_existed = sb.REAL_VAULT.exists()  # existence only; nothing in it is read
    before_vault, before_work = sb.snapshot(), sb.work_snapshot()

    session = sb.run("/capture", "This must not be written anywhere", profile="guard", vault_env=False)

    sb.unchanged(before_vault, session)
    sb.expect(sb.work_snapshot() == before_work, "the working directory changed", session)
    sb.expect(sb.REAL_VAULT.exists() == real_vault_existed,
              "the real vault path appeared or disappeared during the run", session)
    attempted = [name for name, _ in session.tool_uses if name in WRITE_TOOLS]
    sb.expect(not attempted, f"the session tried to use write tools: {attempted}", session)
    # A refused call is only a failure when it aimed outside the temporary root.
    outside = [
        (d.get("tool_name"), hx.paths_outside(json.dumps(d.get("tool_input")), sb.ws.root))
        for d in session.permission_denials
    ]
    outside = [entry for entry in outside if entry[1]]
    sb.expect(not outside, f"the session tried to reach paths outside the temporary root: {outside}", session)
    sb.expect("SECOND_BRAIN_VAULT" in session.all_text,
              "the refusal does not name SECOND_BRAIN_VAULT as the missing setting", session)
