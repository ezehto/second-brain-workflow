# Workflow Review: Design and Development Process

Date: 2026-10-06. Status: findings for review. Nothing in this report has been
applied; each change needs your decision (see [Decisions needed](#10-decisions-needed)).

## Contents

- [1. Summary](#1-summary)
- [2. Evidence this review is based on](#2-evidence-this-review-is-based-on)
- [3. The workflow as it runs today](#3-the-workflow-as-it-runs-today)
- [4. Bottlenecks](#4-bottlenecks)
- [5. Recommendations](#5-recommendations)
- [6. Quality gates that stay](#6-quality-gates-that-stay)
- [7. What agents own and what needs your approval](#7-what-agents-own-and-what-needs-your-approval)
- [8. Quick wins and longer-term changes](#8-quick-wins-and-longer-term-changes)
- [9. Proposed end-to-end workflow](#9-proposed-end-to-end-workflow)
- [10. Decisions needed](#10-decisions-needed)

## 1. Summary

The workflow produces careful work, slowly. Phase 1 has 41 planned tasks; after
two working days 24 of 64 tracked issues are closed, all in the vault and
command half, and no web-app code exists yet. The cause is not a shortage of
agents or tools. It is five habits:

1. **Reviews have no stopping rule.** A change is reviewed until a reviewer
   finds nothing, and reviewers always find something.
2. **Design is finished during implementation.** Rules are discovered by
   reviewers and tests, then written back into the plan.
3. **Every rule lives in several places** (plan, skill, reference file,
   command, test), so one decision costs four or five edits and a test that
   pins the wording.
4. **Acceptance depends on non-deterministic live sessions** that cost money
   and fail intermittently for reasons unrelated to the change.
5. **Work is serial where it could be parallel**, and your decisions arrive
   one at a time, mid-task, where they block.

The recommendations below are mostly rules and small scripts, not new agents.
The three with the largest effect are a severity bar with a two-round review
cap (R1), a short design review before implementation on risky surfaces (R2),
and starting the web-app track in parallel with a decision batch per phase
(R6, R7).

One caution about scope: the six-screen dashboard prototype built today reaches
into Phases 2 to 5 and into data no phase defines. That is useful as design
validation, but it is the same pattern as cause 2 if it turns into requirements
without passing through the plan (R3).

## 2. Evidence this review is based on

All figures come from this repository and this session.

| Fact | Value |
|---|---|
| Phase 1 tasks planned | 41, plus 23 discovered during execution |
| Issues closed / open | 24 / 38 (2 in progress) |
| Commits on `phase-1-foundation` | 14 over two days |
| Phase 1 plan | 2,614 lines |
| `vault_git.py` | 1,318 lines, with 3,021 lines of tests |
| Offline test suite | 1,315 tests, about 2.5 minutes |
| Live command scenarios | 52 sessions per full run, about USD 2 to 3.5 per run; roughly USD 40 to 50 spent so far (my estimate from the per-run cost lines) |
| Review rounds on the create commands (P1-11) | 4 (code review, security review, two re-reviews) |
| Intermittent live failures seen | `/daily` untouched-note scenario failed 1 of 6 runs; `/eod` failed 2 of 5 scenarios in one run before a fix |
| Web-app tasks started | 0 |

Things I did that slowed the work, stated plainly:

- I let review rounds continue on Low findings instead of filing them.
- I committed once with a failing test (a 300-line cap exceeded by one line).
- I cut test output with `tail` and lost the line that explained a failure,
  then paid for more live runs to find it again.
- I did not give you a consolidated list of decisions; several are still open
  from the previous day.
- I pinned skill wording in tests, so each wording fix needs a test edit.

## 3. The workflow as it runs today

```text
Requirements (master prompt, long, all phases at once)
  -> design spec -> your approval
  -> phase plan (2,614 lines, every rule resolved in prose) -> your approval
  -> per task, one at a time:
       writer agent -> orchestrator runs tests
       -> code review (+ security review) -> fix round -> re-review -> ...
       -> live scenarios (twice by the writer, again by the orchestrator)
       -> commit -> close issue
  -> phase summary -> your approval
```

What works and should not change: the vault as source of truth; one writer per
file; the author never reviews; the orchestrator runs the tests itself; Beads
as the persistent tracker; one-line commits on a phase branch; nothing pushed
without being asked.

## 4. Bottlenecks

| # | Bottleneck | Where it shows | Cost |
|---|---|---|---|
| B1 | Open-ended review loops | P1-11 took four review rounds; each round found new Low or Medium wording issues | Hours per task, and each fix risks a new finding |
| B2 | Design discovered in implementation | `vault_git.py` grew to 1,318 lines as reviews found shell-quoting, symlink and FIFO cases | The largest single time sink in Phase 1 |
| B3 | One rule, five homes | The dismissed-capture rule today: plan, skill reference, command, harness test, skill wording test | 4 to 5 edits and a failing test per one-line decision |
| B4 | Non-deterministic acceptance | Live scenarios fail 1 run in 5 or 6 because a session ran a stray shell command | Money, reruns, and doubt about every pass |
| B5 | Serial execution | 40 tasks in a chain; the web app (25 tasks) has not started although it only needs the parser and the fixture | Calendar time |
| B6 | Decisions arrive one at a time | Obsidian checks, git identity, vault-session settings, review bar: all open, each blocking something | Idle or rerouted work |
| B7 | Context is reloaded and lost | A 2,614-line plan, a 358-line global CLAUDE.md, long agent reports; the session has been compacted several times | Slower turns, and facts lost at compaction |
| B8 | Prose rules pinned by tests | `test_skill.py` asserts exact sentences of the skill | A wording improvement breaks a test |
| B9 | Evidence thrown away | Test output cut to the last lines; transcripts not kept | Failures reproduced at cost instead of read |
| B10 | Scope entering sideways | The dashboard prototype grew from 9 Phase 1 pages to six screens spanning Phases 2 to 5 | Risk of building ahead of the plan |

## 5. Recommendations

Effort: S is under an hour, M is half a day, L is more than a day.
Priority: P1 do now, P2 do before Phase 2, P3 when convenient.

### R1. Severity bar and a two-round review cap

- **Current problem:** reviews run until a reviewer finds nothing (B1).
- **Proposed improvement:** a written threat model and severity definitions
  per phase. A change merges when no High or Medium finding is open. Low
  findings become Beads issues in the same step. One review, one confirming
  review of the fixes, then stop; a third round needs your say.
- **Expected benefit:** removes about half the review rounds seen in Phase 1.
- **Tools involved:** project `CLAUDE.md`, master plan "How every phase runs",
  the reviewer brief. No new tooling.
- **Effort:** S. **Priority:** P1.
- **Risk:** a Low finding that mattered is deferred. Mitigation: Lows are
  tracked, and security findings with a concrete attack path are never Low.
- **Trial result:** used today on `/triage`, `/daily`, `/standup` and `/eod`.
  All four were reviewed, fixed and committed in one working session.

### R2. Design review before implementation on risky surfaces

- **Current problem:** security and edge-case rules were found after the code
  existed (B2).
- **Proposed improvement:** for anything that touches a shell, the file
  system outside a sandbox, authentication, or the vault writer, write a
  one-page design (inputs, trust boundary, refusals, what is out of scope) and
  have the security reviewer review that page before any code. The
  implementation review then checks conformance to the page.
- **Expected benefit:** findings arrive when they cost a paragraph, not a
  rewrite. Directly relevant to the vault writer, indexer and login in Gate B.
- **Tools involved:** `security-engineer` and `solutions-architect-reviewer`
  agents, already in use.
- **Effort:** S per surface. **Priority:** P1 (before P1-22, P1-25).
- **Risk:** a design page that is too long becomes a second plan. Cap it at
  one page.

### R3. Prototype findings go through the plan before they become work

- **Current problem:** the prototype now shows workflow stages, rework counts,
  milestones, risks and typed skill links that no phase defines (B10).
- **Proposed improvement:** one plan-gap list (data needed, source, phase or
  "not in plan"), reviewed by you, and each accepted item added to the phase
  that owns it. Nothing from the prototype is built until then. Phase 1's page
  list stays as planned unless you change it.
- **Expected benefit:** keeps the prototype as validation, prevents Phase 1
  from growing.
- **Tools involved:** the six agent reports from today already contain the
  raw list; Beads for the accepted items.
- **Effort:** S to compile, your time to decide. **Priority:** P1.
- **Risk:** none technical. The trade-off is that attractive screens wait.

### R4. One home per rule

- **Current problem:** a rule is restated in plan, skill, reference, command
  and tests (B3, B8).
- **Proposed improvement:** the skill's reference files are the single source
  for behaviour rules. The plan records the decision and its reason in one
  line and links to the reference. Commands point at a section and do not
  restate it. Tests assert behaviour (what ends up in the vault), and assert
  wording only for a short list of safety sentences.
- **Expected benefit:** a decision costs one edit; wording can improve without
  breaking tests.
- **Tools involved:** none new. A one-off pass by the skill owner and the
  harness owner.
- **Effort:** M. **Priority:** P2.
- **Risk:** the plan becomes less self-contained. Acceptable: the skill ships
  with the product and the plan does not.

### R5. Make acceptance cheap and deterministic

- **Current problem:** live scenarios are slow, paid and intermittent (B4, B9).
- **Proposed improvement:**
  1. Offline suite on every change (already fast).
  2. Live scenarios once per task group, by the orchestrator only, not twice
     by the writer and again by the orchestrator.
  3. A scenario that fails on a stray command is retried once automatically
     and reported as "flaky", separately from a behaviour failure.
  4. Full logs of every live run kept on disk under the job folder; never cut
     the output when capturing.
  5. Where possible, block stray commands with the session's permission rules
     (planned for P1-15) so the failure cannot happen, and test that
     the rule exists offline.
- **Expected benefit:** roughly a third of the live-run cost, and failures can
  be read instead of reproduced.
- **Tools involved:** the existing pytest harness; a small change to its
  failure classification.
- **Effort:** M. **Priority:** P1 for items 2 and 4, P2 for the rest.
- **Risk:** fewer live runs means a rare behaviour failure can slip through.
  Mitigation: the week of real use at the end of the phase is the real test.

### R6. Run the web-app track in parallel

- **Current problem:** 25 web-app tasks wait behind command work they do not
  depend on (B5).
- **Proposed improvement:** two tracks. Track A finishes the commands
  (install, smoke test). Track B starts now with the scaffold, models and
  indexer, in a git worktree so the two never share uncommitted files.
  Within Track B, the writer and the indexer run in parallel after the models,
  and frontend pages run in parallel once the OpenAPI contract is committed,
  as the plan already allows.
- **Expected benefit:** the largest calendar saving available.
- **Tools involved:** worktree isolation for agents; `devops-cloud-engineer`,
  `backend-engineer-python`, `frontend-engineer`.
- **Effort:** S to start. **Priority:** P1, once you decide on the Obsidian
  checks (see section 10).
- **Risk:** two tracks double the review load on you at phase end, and a
  failed mount spike check would send Track B back. The spike already passed
  its automated measurements; only the four manual Obsidian checks are open.

### R7. One decision batch per phase, asked once

- **Current problem:** decisions surface mid-task and block (B6).
- **Proposed improvement:** at the start of each phase, and whenever three or
  more accumulate, one list: the decision, the options, my recommendation, and
  what it blocks. Work that does not depend on an answer continues.
- **Expected benefit:** you spend one sitting instead of many interruptions;
  nothing waits silently.
- **Tools involved:** Beads label `needs-decision`; a section in the phase
  summary.
- **Effort:** S. **Priority:** P1. Section 10 is the first batch.
- **Risk:** none.

### R8. Size tasks and flag overruns

- **Current problem:** no task has an estimate, so nothing signals that a
  task has run long.
- **Proposed improvement:** each task gets a size (S, M, L) when planned. At
  twice its size the orchestrator stops and reports: continue, cut scope, or
  replan. This is the plan's own "three failures trigger a replan" rule
  applied to time.
- **Expected benefit:** overruns like `vault_git.py` are caught at 2x, not 6x.
- **Tools involved:** a Beads field or label.
- **Effort:** S. **Priority:** P2.
- **Risk:** estimates are rough. They only need to be good enough to trip a
  flag.

### R9. Smaller context per task

- **Current problem:** agents and the orchestrator load a 2,614-line plan and
  long instruction files; context is compacted and facts are lost (B7).
- **Proposed improvement:**
  1. Task briefs name sections, not files, and agents read only those.
  2. Agent reports follow a fixed short shape: status, what changed, test
     result lines, open items. Details stay in files.
  3. Decisions and environment facts are written to Beads or the plan the
     moment they are made, not kept in conversation.
  4. One shared brief file for parallel agents (used today for the six design
     agents) instead of repeating rules in each prompt.
  5. Split the phase plan: a short task list plus one reference file per
     topic, so a task loads a few hundred lines.
- **Expected benefit:** faster turns, fewer compactions, consistent agents.
- **Tools involved:** none new. Optionally `graphify` to answer structure
  questions without reading files.
- **Effort:** S for items 1 to 4, M for item 5. **Priority:** P2.
- **Risk:** an agent misses a rule in a section it was not pointed at. The
  review catches it; the brief is then corrected.

### R10. Automate the repetitive checks

- **Current problem:** the same manual steps recur: delete `__pycache__`,
  check for dashes, check the 300-line skill cap, check every Markdown doc has
  a table of contents, confirm tests pass before commit.
- **Proposed improvement:** one `scripts/precommit.sh` that runs them and the
  offline suite, called by the orchestrator before every commit; later a git
  pre-commit hook. Raise or drop the 300-line skill cap: it has cost more than
  it protects.
- **Expected benefit:** removes a class of small mistakes, including the
  failing-test commit.
- **Tools involved:** a shell script; optionally a Claude Code hook.
- **Effort:** S. **Priority:** P1.
- **Risk:** a slow hook is skipped. Keep it under three minutes.

### R11. Design before building UI

- **Current problem:** the first prototype was generic and had to be
  restyled; none of today's screens has been looked at in a browser.
- **Proposed improvement:** for UI work: agree the direction on one screen
  first, then fan out; always use the `frontend-design` skill (now a global
  rule); and add one visual check before you are asked to review, using the
  Playwright tools already installed.
- **Expected benefit:** you review screens that are known to render.
- **Tools involved:** `frontend-design` skill, Playwright MCP, `dataviz` skill.
- **Effort:** S. **Priority:** P2 (P1 for the current prototype: see
  section 10).
- **Risk:** the design tool's own instructions say not to render without your
  request, so this needs your standing permission.

### R12. Knowledge that can be found again

- **Current problem:** decisions sit in a long plan and in closed issues;
  lessons from execution sit in conversation.
- **Proposed improvement:** a short decision log (`docs/decisions.md`, one
  line per decision with date and link), kept current as decisions are made;
  lessons from each phase written into the phase summary; and, once the vault
  commands are installed, record this project's own decisions and lessons in
  the vault with `/decision` and `/knowledge`. The system should run on
  itself.
- **Expected benefit:** retrieval by reading 50 lines instead of searching
  2,600.
- **Tools involved:** the project's own commands; Beads.
- **Effort:** S. **Priority:** P2.
- **Risk:** a second place for decisions. Keep it an index with links, not a
  copy.

### What I do not recommend

- **More agents or a multi-agent workflow engine.** Six agents in parallel
  worked today because each owned one file. More would not have helped the
  command work, which was serial by nature.
- **More MCP servers.** Several are configured and unused; two fail to
  connect. Each adds context and failure modes.
- **A CI service now.** There is one developer and nothing is pushed. A local
  pre-commit script gives the same protection.

## 6. Quality gates that stay

| Gate | Why it stays |
|---|---|
| Your approval of each phase design, phase plan and phase result | The product is yours; scope is decided here |
| The author never reviews its own change | Fresh context catches what the author rationalised |
| Security review of anything touching a shell, the file system, login or the vault writer | The vault holds your work; a mistake here is not recoverable by a retry |
| The orchestrator runs the tests and reads the output | An agent's "tests pass" is a claim |
| Tests written with the change; the rebuild-invariant test for the index | The plan's central promise is that the database can be rebuilt |
| No open High or Medium finding at commit | The severity bar of R1 |
| Nothing pushed, installed into `~/.claude`, or written to the real vault without your say | Outward-facing or hard to reverse |
| One week of real use before the next phase | The only test of whether it helps your day |

## 7. What agents own and what needs your approval

| Agents own, no approval | Agents propose, you approve | Always you |
|---|---|---|
| Implementation inside an approved task | A change to the plan, spec or a decided rule | Phase start and phase approval |
| Tests, test fixes, flaky-test classification | A new dependency or tool | Pushing, merging to `main` |
| Code review and security review | Deferring a Medium finding | Installing into `~/.claude`; first write to the real vault |
| Low findings filed as issues | A third review round | Anything touching work accounts (Phase 4 policy) |
| Local commits on the phase branch | Scope added from a prototype (R3) | Choosing between options that change the product |
| Documentation that follows the code | Skipping a gate once, with the reason | Deleting or moving vault notes |

## 8. Quick wins and longer-term changes

| Change | Effort | Impact | When |
|---|---|---|---|
| R1 severity bar and review cap | S | High | Now |
| R7 decision batch | S | High | Now (section 10) |
| R10 pre-commit script, drop the 300-line cap | S | Medium | Now |
| R5 items 2 and 4: one live run, keep logs | S | Medium | Now |
| R3 plan-gap list from the prototype | S | High | Now |
| R6 parallel web-app track | S to start | High | After your answer on the Obsidian checks |
| R2 design review on risky surfaces | S each | High | Before P1-22 and P1-25 |
| R8 task sizes | S | Medium | Before Phase 2 planning |
| R9 context per task | S to M | Medium | Before Phase 2 |
| R4 one home per rule | M | Medium | Before Phase 2 |
| R11 visual check for UI | S | Medium | Before the frontend tasks |
| R12 decision log, use the vault for this project | S | Medium | When commands are installed |

## 9. Proposed end-to-end workflow

```text
PHASE START
  Requirements and open questions
    -> one decision batch to you ............................ [YOU: answer once]
  Phase design delta (short)
    -> architecture review, security review of risky surfaces  (parallel)
    -> ...................................................... [YOU: approve]
  Task list with sizes, dependencies and parallel tracks
    -> ...................................................... [YOU: approve]

PER TASK (tracks run in parallel; one writer per file)
  Brief (sections to read, acceptance, size)
    -> risky surface? one-page design -> security review of the page
    -> implement with tests ................................. [agent]
    -> pre-commit script: offline tests, lint, doc checks .... [automatic]
    -> code review  ||  security review (if relevant) ....... [agents, parallel]
    -> High or Medium findings? fix -> one confirming review
         Low findings -> filed as issues, not fixed now
         third round or 2x size -> stop ..................... [YOU: decide]
    -> orchestrator runs acceptance once, keeps full logs
    -> local commit, issue closed with notes

PER TASK GROUP
  Live scenarios once; flaky failures retried once and reported separately

PHASE END
  Summary: what was built, test evidence, open issues, lessons, plan gaps
    -> ...................................................... [YOU: approve]
  Install or deploy ......................................... [YOU: go-ahead]
  One week of real use -> next phase
```

Parallel points: design reviews; code and security review; independent tracks
(commands, backend, frontend after the API contract); independent files within
a track. Never parallel: two writers on one file, or a task and the task it
depends on.

## 10. Decisions needed

This is the first decision batch (R7). My recommendation is first in each row.

| # | Decision | Options | Blocks |
|---|---|---|---|
| D-A | Adopt R1 (severity bar, two-round cap) in project `CLAUDE.md` and the master plan | Adopt / adopt with changes / keep as is | Every remaining review |
| D-B | Start the web-app track now, in parallel | Start now; do the four Obsidian checks when convenient / wait for the checks | 25 tasks |
| D-C | The four Obsidian checks in `docs/spikes/phase-1-mount-spike.md` section 7 | You run them (about 15 minutes) / skip and accept the risk | P1-05, and confidence in D-B |
| D-D | Global git identity (`git config --global user.name`, `user.email`) | Set it / keep repo-local only | P1-05 vault creation |
| D-E | How vault sessions are launched, for the permission settings | A launcher script with its own settings file / settings in the vault folder / global | P1-15 install |
| D-F | Install the nine commands into `~/.claude` and smoke-test on the real vault | Go ahead after D-D and D-E / wait | P1-15, then real use |
| D-G | Dismissed captures keep only `status: dismissed` | Keep / also write the classification | The triage API |
| D-H | Prototype scope: which of the six screens' new data becomes planned work | Review the plan-gap list first (R3) / Phase 1 stays as planned | Phase 1 page list |
| D-I | Permission to render the prototype in a browser before you review it | Yes, standing / ask each time | Prototype quality |
| D-J | Test transcript folders under `~/.claude/projects/` | Delete after each run / keep 7 days / leave | Disk and privacy |
| D-K | Drop the 300-line cap on the skill file | Drop / raise to 400 / keep | Skill edits |
