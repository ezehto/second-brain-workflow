# Phase 1: Foundation, Task-Level Plan

| | |
|---|---|
| Status | Revised 2026-10-05 after the user's decisions and the architecture review ("approve with changes"); awaiting approval |
| Date | 2026-10-05 |
| Phase | 1 of 6 (see [`master-plan.md`](master-plan.md#phase-1-foundation)) |
| Design | [`../specs/2026-10-01-second-brain-design.md`](../specs/2026-10-01-second-brain-design.md), including decisions C14 to C24 |
| Tracking | beads, prefix `sbw`, one epic for Phase 1, one issue per task below |

This plan turns the 11 master-plan steps for Phase 1 into 41 tasks. Each task
is sized for one specialist agent in one session and can be reviewed and tested
on its own. The decisions the user confirmed on 2026-10-05 are recorded in the
design (C14 to C24) and summarised in
[Decisions confirmed 2026-10-05](#12-decisions-confirmed-2026-10-05).

## Contents

- [1. How to read this plan](#1-how-to-read-this-plan)
  - [Gates](#gates)
  - [Conventions used in task entries](#conventions-used-in-task-entries)
- [2. Resolved details](#2-resolved-details)
  - [2.1 `project` value and slug rule](#21-project-value-and-slug-rule)
  - [2.2 Standup carry-forward semantics](#22-standup-carry-forward-semantics)
  - [2.3 Status vocabulary per type](#23-status-vocabulary-per-type)
  - [2.4 Locating a heading for "append to section"](#24-locating-a-heading-for-append-to-section)
  - [2.5 File-name sanitising, collisions and emitted links](#25-file-name-sanitising-collisions-and-emitted-links)
  - [2.6 Vault git configuration](#26-vault-git-configuration)
  - [2.7 Poll interval and scan budgets](#27-poll-interval-and-scan-budgets)
  - [2.8 Wikilink resolution rules](#28-wikilink-resolution-rules)
  - [2.9 Other defaults this plan fixes](#29-other-defaults-this-plan-fixes)
  - [2.10 Parsing details: types, tags and dates](#210-parsing-details-types-tags-and-dates)
  - [2.11 Conformance checker rules](#211-conformance-checker-rules)
  - [2.12 Test clock](#212-test-clock)
  - [2.13 Triage rules](#213-triage-rules)
- [3. Templates](#3-templates)
  - [3.1 Placeholder subset](#31-placeholder-subset)
  - [3.2 Template content](#32-template-content)
  - [3.3 Obsidian settings for the vault](#33-obsidian-settings-for-the-vault)
- [4. Command contracts](#4-command-contracts)
  - [4.1 Command details](#41-command-details)
  - [4.2 `vault_git.py`: the only way a command runs git](#42-vault_gitpy-the-only-way-a-command-runs-git)
- [5. API surface](#5-api-surface)
- [6. Repository layout and Compose](#6-repository-layout-and-compose)
  - [Test isolation](#test-isolation)
  - [The e2e stack](#the-e2e-stack)
- [7. Pinned versions](#7-pinned-versions)
- [8. Mount spike procedure](#8-mount-spike-procedure)
- [9. Tasks](#9-tasks)
  - [Step 1: Prerequisites and mount spike](#step-1-prerequisites-and-mount-spike)
  - [Step 2: Vault](#step-2-vault)
  - [Step 3: Skill, commands, fixture, parser, checker](#step-3-skill-commands-fixture-parser-checker)
  - [Step 4: Repository scaffold](#step-4-repository-scaffold)
  - [Step 5: Index models](#step-5-index-models)
  - [Step 6: Indexer](#step-6-indexer)
  - [Step 7: Vault writer](#step-7-vault-writer)
  - [Step 8: API](#step-8-api)
  - [Step 9: Frontend](#step-9-frontend)
  - [Step 10: End-to-end tests and README](#step-10-end-to-end-tests-and-readme)
  - [Step 11: Real use and phase review](#step-11-real-use-and-phase-review)
- [10. Dependencies and parallelism](#10-dependencies-and-parallelism)
  - [Dependency table](#dependency-table)
  - [Graph](#graph)
  - [Parallel waves](#parallel-waves)
  - [Critical path](#critical-path)
- [11. Risks specific to this breakdown](#11-risks-specific-to-this-breakdown)
- [12. Decisions confirmed 2026-10-05](#12-decisions-confirmed-2026-10-05)
- [13. Verification record](#13-verification-record)

---

## 1. How to read this plan

### Gates

Docker is not usable inside WSL until the user enables Docker Desktop WSL
integration. The tasks are therefore split by two gates.

| Gate | Opens when | Tasks behind it |
|---|---|---|
| **A: no Docker needed** | Now | P1-03 to P1-15: templates and skill, vault init, the real vault, golden fixture, the Markdown and frontmatter **parser** (P1-07, built in WSL with `uv`, decision C15), the conformance checker that imports it, the install script, the nine commands and their tests. These use only WSL Python 3.12, `uv`, `git` and Claude Code. |
| **B: mount spike passed** | P1-02 records a pass (section 8) | Every other build task: P1-16 to P1-41. This includes the writer; only the parser is allowed ahead of the spike. |

P1-01 (user enables Docker) and P1-02 (mount spike) sit between the gates. Gate
A work and the spike can run at the same time.

### Conventions used in task entries

- **Agent**: the implementing specialist. Two tasks are user actions and one
  needs the user's go-ahead; they are marked "user, orchestrator verifies",
  because no agent can operate Docker Desktop settings or the Obsidian UI.
- **Reviewers**: `code-reviewer` on every task. `security-engineer` is added
  for authentication, the vault writer, secrets handling and anything touching
  the filesystem boundary (vault writes, the install script writing into
  `~/.claude`, bind mounts, git in the vault). The spike scripts get
  `code-reviewer` only.
- **Tests first**: the failing tests the implementer writes before the code.
  The orchestrator runs the **Run** command itself and reads the output.
- **Acceptance**: every criterion is checkable by running something.
- Backend tests run in the `test` Compose service, which has no vault mount
  (section 6): `docker compose --profile test run --rm test ...`. Frontend
  commands: `docker compose run --rm frontend ...`. Gate A commands run in WSL
  with `uv`.
- No test ever touches `/mnt/d/Second Brain`, and nothing in this plan reads or
  touches `/mnt/c/Users/User/Documents/Obsidian Vault`.

---

## 2. Resolved details

Each item from the design's "Details the Phase 1 plan must define" list, with
the rule and a one-line reason, updated for decisions C14 to C24.

### 2.1 `project` value and slug rule

| Rule | Detail |
|---|---|
| Written form (C19) | The writer and the commands write `project: "[[<Project title>]]"`, or the folder-qualified `project: "[[02-Work/Projects/<Project title>]]"` when the stem is not unique on disk (section 2.5). The templates keep `project:` empty. |
| Accepted hand-typed forms | A wikilink as above, with or without alias, or a plain slug (`project: loadup`). |
| Slug function | `slugify(s)`: Unicode NFKD, drop combining marks, lower-case, replace every run of characters outside `[a-z0-9]` with `-`, trim leading and trailing `-`. `"LoadUp"` → `loadup`; `"Strato GIDA v2"` → `strato-gida-v2`. |
| A project's slug | `slugify(file name stem)` of a note with `type: project`. No separate `slug` key. |
| Indexed value | If the value is a wikilink: drop brackets, alias, heading and any folder prefix, then `slugify`. Otherwise `slugify` the value. The promoted `project` column stores the slug; the raw value stays in `frontmatter`. |
| Resolution | At query time: the project note whose slug equals the indexed value. |
| No match | Listed under "unknown project slugs" on the Index Status page. Not an error. |
| Two project notes with the same slug | Neither resolves; both are listed under "duplicate project slugs". Creating a project through the writer or `/project` is rejected if a project note with the same slug exists in `02-Work/Projects/` (filesystem check). |
| Project given by slug on create | The writer and the commands find the project note on disk; if none exists the request is rejected (`422`, or the command lists the known projects). |
| Renaming a project note | Obsidian updates wikilinks in frontmatter, so wikilink-valued `project` keys follow the rename; plain slugs typed by hand become unknown and show on the Index Status page. |

Reason: a wikilink gives the relationship an edge in Obsidian's graph and
survives renames, while a slug derived from the file name is still the one key
every project note is guaranteed to have.

### 2.2 Standup carry-forward semantics

"Today" is the date in `TZ=Asia/Manila`, or the pinned test date of section
2.12. Carry-forward fills today's daily
note in one of two cases:

1. **Today's note does not exist**: it is created from the template and filled.
2. **Today's note exists and is untouched** (review M-1): it is filled in place
   through the writer (or the command's own edit) with the on-disk hash check.
   For the writer that is the hash comparison of the design's write-safety
   rules. For a command it means: immediately before writing, re-read the file
   and confirm it is byte-identical to the content judged untouched; if it
   differs, treat the note as touched and leave it unchanged.
   This covers Obsidian's Daily notes plugin having created the note first.

**Untouched** is defined against the **current** vault template
(`08-System/Templates/daily.md`), because the user may edit it: render that
template's body (everything after its frontmatter) for the note's date, then
compare it with the note's body (everything after the note's frontmatter),
ignoring all whitespace differences. Equal means untouched; the frontmatter
must also parse with `type: daily`. Frontmatter is excluded from the
comparison because `id` and `created` depend on the moment of creation and
Obsidian may reformat it. Any other difference means **touched**, and the note
is returned unchanged; nothing is regenerated or merged. Carry-forward items
are inserted under whichever of the six standup headings exist in the note
(section 2.4 rule 6 adds any that a customised template dropped).

Filling a note that Obsidian has open relies on spike measurement M5b (atomic
replace over a file open in Obsidian) as its evidence. The design's accepted
residual risk applies here too: if the user is typing in that note at the same
moment, Obsidian's autosave can overwrite the fill; the hash check catches an
edit that is already on disk, and the vault's git history makes any loss
recoverable.

Before building carry-forward, the API runs one sync pass under the indexer's
advisory lock (review S-6), so a task marked done in Obsidian seconds earlier
is not carried. Commands read task notes from disk directly.

Inputs: the task notes, and the **previous daily note** `P`: the daily note
with the latest date strictly before today (weekends and gaps are handled).

| Section | Content |
|---|---|
| Done | Empty. Nothing is assumed complete. |
| Today | 1. Task items: `- [ ] [[Task]]` for every task with status `in-progress`, then `review`, then `planned` with a valid `due` on or before today. Within each status: `due` ascending (no valid due last), then title, then path. 2. Then free-text items: every unchecked `- [ ]` item from `P`'s **Today** section that contains no wikilink to a task note, copied verbatim, in the order they appear in `P`. |
| Blockers | `- [[Task]]` for every task with status `blocked`, followed by ` (blocked by: <value>)` when `blocked_by` is set. Ordered as task items in Today: `due` ascending (no valid due last), then title, then path. |
| Decisions / Updates | Empty. |
| Follow-ups | Every unchecked `- [ ]` item from `P`'s **Follow-ups** section, copied verbatim in the order they appear in `P`, **including items that link a task** (the task-link rule below applies to Today only). |
| Related Tasks / Projects | `- [[Project]]` for each distinct resolved project of the task items placed under **Today and Blockers**, sorted by project title, then path. Projects of free-text items are not considered; unknown or duplicate project slugs are skipped. |

Rules:

- **Task status is authoritative for task links in Today; checkboxes are
  authoritative for free text.** An unchecked item in `P`'s Today section that
  contains a wikilink resolving (section 2.8, including "ambiguous") to a note
  with `type: task` is dropped, because the task's current status already
  decides whether it is carried. An unresolved link does not count; such an
  item is free text. Reason: a stale checkbox must not resurrect a task closed
  in Obsidian.
- **Follow-ups are always copied** when unchecked, even if they link a task.
  Reason: a follow-up is a separate action about the task, it exists nowhere
  else in today's note, and dropping it would assume completion.
- **Duplicates are removed within a section only**, keeping the first
  occurrence. The key is the task's path for task items, and for free-text
  items the text after `- [ ] ` with whitespace runs collapsed and both ends
  trimmed (case-sensitive). Nothing is de-duplicated across sections; a task
  cannot appear in two sections because its status puts it in exactly one.
  Reason: one key per section is easy to apply identically in code and prose.
- An unchecked item is a line matching `- [ ] ` (also `* [ ] ` and `+ [ ] `,
  any indentation, which is kept). `- [x]` and `- [X]` are checked and never
  carried; any other marker (`- [/]`, `- [-]`) counts as checked. Reason:
  Obsidian treats only a space as unchecked.
- Tasks with status `inbox`, `done`, `cancelled`, and `planned` tasks with no
  valid due date or a future one are not carried. A `due` that cannot be
  parsed (section 2.10) counts as no valid due date, so such a `planned` task
  is **not** carried. Reason: carrying on a guessed date would invent a
  deadline; the note is listed under "invalid dates" on the Index Status page
  so the user can fix it.
- Links emitted follow section 2.5 (folder-qualified when the stem is not
  unique on disk).

Reason: deriving work from task status keeps the vault the source of truth,
copying free-text checkboxes keeps the small items that never became tasks,
and the untouched rule makes the result the same whether Obsidian, a command
or the app opened the day.

The golden fixture (P1-06) holds three scenarios under
`expected/carry-forward/`: `new-note` (no note yet), `untouched-note` (an
untouched note created by Obsidian) and `touched-note` (a note the user has
typed in, which must come back unchanged), each with the expected output. The
commands (P1-13) and the API (P1-29) are tested against all three.

### 2.3 Status vocabulary per type

| Type | Statuses | Default on create |
|---|---|---|
| `task` | `inbox`, `planned`, `in-progress`, `blocked`, `review`, `done`, `cancelled` (fixed by the design) | `planned` |
| `project` | `active`, `paused`, `done`, `archived` | `active` |
| `decision` | `proposed`, `accepted`, `superseded`, `rejected` | `proposed` |
| `lesson` | `active`, `archived` | `active` |
| `capture` | `inbox`, `triaged`, `dismissed` | `inbox` |
| `daily` | no `status` key | n/a |
| `note` (no frontmatter, no usable `type`, or malformed frontmatter) | none enforced | n/a |
| any other `type` value | none enforced | n/a |

- Unknown `type` values are indexed as written, trimmed and lower-cased (section 2.10),
  not as `note`; they have no status vocabulary.
- The indexer stores any status value as-is; values outside the vocabulary are
  counted under "unknown statuses" on the Index Status page.
- The API's status-change endpoint and the commands accept only the vocabulary
  for the note's type.
- Nothing is deleted: `cancelled`, `archived` and `dismissed` replace deletion.

The vocabulary lives in one place, `backend/vault/conventions.py` (built with
the parser in P1-07); the checker, writer, indexer and API import it, and the
skill's reference restates it for the commands.

Reason: each list is the smallest set that answers the dashboard questions for
that type.

### 2.4 Locating a heading for "append to section"

1. Skip the frontmatter block and every fenced code block (```` ``` ```` or
   `~~~`). Only ATX headings (`#` to `######` followed by a space) count;
   Setext headings are not recognised.
2. The target is given as level and text, for example `## Today`. A heading
   matches when its level is equal and its text, with surrounding whitespace
   and trailing `#` characters removed, is equal under Unicode casefold.
3. If several headings match, the **first** one is used.
4. The section ends just before the next heading of the same or a higher level
   (fewer or equal `#`), or at end of file.
5. Insertion point: after the last non-blank line of the section. Exactly one
   blank line is kept before the next heading. An empty section receives the
   text after one blank line below the heading.
6. If no heading matches, the heading is appended at the end of the file at the
   requested level, followed by the text, and the API response says
   `section_created: true`.
7. The file's existing line endings and BOM are preserved. The line ending is
   that of the file's first line break (`\r\n` means CRLF); a file with no line
   break uses LF.
8. **End of file.** When the insertion point is the end of the file (the target
   section is last, or rule 6 applies): trailing blank lines at the end of the
   file are removed; if the last remaining line has no line ending, one is
   added; for rule 6 exactly one blank line is written before the new heading;
   then the new text is written, and the file ends with **exactly one** line
   ending. Nothing earlier in the file changes. Reason: one fixed end state is
   the only result that code and a Claude session produce identically, and it
   is what Obsidian itself writes.

Reason: these are the rules a person reading the file would apply, they need no
Markdown AST, and rule 6 means a renamed heading never loses appended text.

### 2.5 File-name sanitising, collisions and emitted links

Sanitising, applied by the writer and the commands whenever they derive a file
name from a title. Daily notes are exempt (always `YYYY-MM-DD.md`).

1. Normalise to Unicode NFC.
2. Remove control characters (U+0000 to U+001F, U+007F).
3. Replace each of `\ / : * ? " < > |` (Windows-illegal) and `# ^ [ ]`
   (break Obsidian links) with a space.
4. Collapse whitespace runs to one space; trim both ends.
5. Strip leading dots (a leading dot would hide the file and look like a
   writer temp file) and trailing dots and spaces (Windows strips them).
6. If the stem, case-insensitively, is a Windows reserved device name (`CON`,
   `PRN`, `AUX`, `NUL`, `COM1` to `COM9`, `LPT1` to `LPT9`), append ` note`.
7. Truncate the stem to 100 characters (code points, never splitting a
   surrogate pair), then trim again. The full vault-relative path must be at
   most 200 characters, keeping `D:\Second Brain\...` under the Windows
   260-character limit; longer paths are rejected.
8. An empty result becomes `Untitled YYYY-MM-DD HHmmss`.
9. Captures are named `YYYY-MM-DD HHmm <first 8 words of the text>`.

The character sets in rules 2, 3 and 6 are constants in
`backend/vault/conventions.py`.

Collisions (C22):

- **Same folder, case-insensitive**: a create whose name equals an existing
  file's name case-insensitively is rejected (`409`; the command asks for a
  different title). For captures only, one retry with seconds appended
  (`HHmmss`) is made first. Checked against the filesystem at write time.
- **Same name in a different folder**: allowed.
- Uniqueness checks always read the filesystem, never the index, so a check
  cannot be wrong by a poll interval.

Missing folders: the writer and the commands create a note's parent folder
when it does not exist, but only when it is a Phase 1 folder of design
section D or a year folder `01-Daily/YYYY`. The init script creates only the
current year's folder and git does not track empty folders, so a folder can be
absent after a new year or a `git clean`. Any other missing folder is an error,
never created. The command scenarios (P1-10, P1-13) and the writer tests
(P1-22) assert both cases.

Emitted links (C22): whenever the writer or a command writes a wikilink (in
`project`, `triaged_to`, carry-forward items, `## Links`), it first checks
whether the target's stem is unique on disk among non-ignored `.md` files,
case-insensitively. If it is, it writes `[[Name]]`; if not, it writes the
vault-relative path without `.md`: `[[02-Work/Tasks/Name]]`. One directory
walk per operation is enough; its result is reused for every link in that
operation.

Spike finding (M11, 2026-10-05): drvfs does not refuse `:` or `?` in a name
created from WSL or a container; it stores a private-use substitute character
(U+F03A, U+F03F) that Windows shows as a different name. Rule 3 is therefore
the only protection: the filesystem will not reject such a name.

Reason: rules 3 to 7 cover what Windows, drvfs and Obsidian each refuse or
mangle; allowing duplicates across folders matches how Obsidian is used, and
folder-qualified links keep everything the system writes unambiguous.

### 2.6 Vault git configuration

Applied by the vault init script (P1-04), then verified:

| Setting | Value | Reason |
|---|---|---|
| `git init -b main` | | One branch, no workflow. |
| `core.autocrlf` | `false` | Bytes on disk are what Obsidian wrote; no conversion. |
| `core.filemode` | `false` | drvfs and container writes report mode bits that mean nothing on NTFS. |
| `core.quotepath` | `false` | Unicode note names readable in `git status`. |
| `user.name`, `user.email` | Copied into the repo's local config from the user's global git config at init time | Commits from `/eod` are attributed; fails loudly if global config is missing. |
| Remote | None. The init script and `/eod` verify `git remote` is empty and refuse to continue otherwise. | Notes never leave the machine (C2). |
| `.gitattributes` | `* -text` (review S-8) | No line-ending normalisation; consistent with `core.autocrlf=false` and with the writer keeping a file's existing CRLF. |
| `.gitignore` | `.obsidian/workspace*.json`, `.obsidian/cache/`, `.trash/`, `.*.sbw-tmp-*`, `.DS_Store`, `Thumbs.db`, `desktop.ini` | Machine-local UI state, deleted notes, writer temp files and OS litter are not history. The rest of `.obsidian/` is committed so plugin settings are versioned. |
| Which git | WSL `git` only. Windows git (or an Obsidian git plugin) is not used on this repo. | Two git implementations disagree on stat data on drvfs. |
| Obsidian Sync | Off (C14). | Decided by the user; nothing to exclude. |

The app never runs git (C11). The only git writers are the init script (one
initial commit) and `/eod`.

### 2.7 Poll interval and scan budgets

| Item | Value |
|---|---|
| Poll interval | `INDEXER_POLL_SECONDS=10` in `.env` (default 10), or the value the spike sets (section 8, M1). |
| Change detection | Each pass walks the vault (honouring the ignore rules), `stat`s every `.md` file and compares `(mtime_ns, size)` with the index. Only changed, new and missing files are read, hashed (SHA-256 of raw bytes) and parsed. |
| Racy files | No clock comparison. Every file that a pass read (because it was new or its `(mtime_ns, size)` changed) is read and hashed again on the next pass, whatever its stat says, and only then trusted by stat alone. This catches a second write that left `(mtime_ns, size)` unchanged. It is deliberately independent of the difference between Windows-stamped mtimes and the WSL clock, which the spike (2026-10-05) measured over 11 minutes as a sawtooth: drifting about 0.105 s per second and stepping back about 3 s every 33 s, between -1.74 s and +1.32 s. That is one session on one boot, so the difference is treated as unbounded and no fixed window is relied on. The spike also showed stamped mtime resolution no coarser than about 7 ms (stored in 100 ns units), far below the poll interval. |
| Budget: steady-state pass (nothing changed) | Target at most 3 s at 1,000 notes; must stay under the poll interval at 1,000 notes. The 5,000-note projection from the spike is recorded as a risk, not a gate. |
| Budget: full `reindex` | Target at most 30 s at 1,000 notes; the 5,000-note projection is recorded. |
| Overrun | Each pass logs one JSON line with duration, files scanned, changed, added, removed. A pass over budget logs a warning; it is not an error. |
| Concurrency | The poll loop, `POST /api/index/refresh/`, the standup sync pass and the writer's single-file re-index serialise on one PostgreSQL advisory lock. |

Reason: 10 s means an Obsidian edit reaches the dashboard before the user
switches windows; the old vault has 154 notes, so 1,000 is the realistic
horizon for gating and 5,000 is headroom to watch.

### 2.8 Wikilink resolution rules

Extraction (indexer):

- Wikilinks are taken from the body and from every string value in the
  frontmatter (including list items). Text inside fenced code blocks and inline
  code spans is skipped.
- Phase 1 indexes wikilinks only. Markdown links (`[text](file.md)`) are not
  indexed.
- Each link is normalised to a `target_title`:

| Form | Stored target |
|---|---|
| `[[A]]` | `a` |
| `[[A\|alias]]`, including an escaped pipe inside a table | `a` (display text dropped) |
| `[[A#Heading]]`, `[[A#^block]]` | `a` (heading and block dropped) |
| `[[#Heading]]` | not stored (link to the same note) |
| `![[A]]` (embed) | `a`, stored like a link |
| `[[folder/A]]` | `folder/a` |
| `[[A.md]]` | `a` (`.md` stripped) |
| `[[image.png]]`, `![[file.pdf]]` (a known attachment extension) | not stored (attachments are not notes). The extensions are a fixed list in `conventions.py`, matched case-insensitively on the final path segment: `png`, `jpg`, `jpeg`, `gif`, `bmp`, `svg`, `webp`, `avif`, `pdf`, `mp3`, `wav`, `m4a`, `ogg`, `flac`, `3gp`, `mp4`, `webm`, `mov`, `mkv`, `ogv`, `canvas`, `base`. Any other dotted name is a note title, so `[[Notes on Node.js]]` and `[[Version 2.0]]` are note links |

Normalisation: NFC, casefold, trim, collapse internal whitespace, strip `.md`,
use `/` as separator.

Link set: the index stores **one `Link` row per distinct `(source note,
target_title)` pair**. Repeated links to the same target, and a link plus an
embed of it, collapse into one row; links whose spellings normalise to the same
target (`[[A]]`, `[[a|x]]`, `[[A#H]]`) also collapse. The note detail's `links`
map keeps one entry per spelling as written, each pointing at the same
resolution. Reason: backlinks and resolution only need "does A link B", and a
set is order-free, so the rebuild invariant cannot depend on link order.

Resolution (at query time, as the design requires):

1. A target containing `/` matches the note whose vault-relative path without
   `.md`, casefolded, equals the target or ends with `/<target>`.
2. A bare target matches every note whose casefolded stem equals it.
3. Exactly one match: **resolved**.
4. More than one match: **ambiguous**. It resolves deterministically to the
   match with the shortest vault-relative path, ties broken by lexicographic
   path order, and is flagged on the Index Status page and in the note detail.
   This rule is the app's own; it does not claim to reproduce how Obsidian
   picks among duplicates, and the "ambiguous" flag is how the difference is
   made visible (review O-9).
5. No match: **unresolved**, shown as such, not an error.
6. Frontmatter `aliases` are not used for resolution.

Links written by the system itself are folder-qualified whenever a stem is
duplicated (section 2.5), so ambiguity can only come from hand-written links.

Reason: deterministic resolution keeps the rebuild invariant true even with
duplicate names, and flagging ambiguity is more honest than guessing.

### 2.9 Other defaults this plan fixes

| Topic | Default | Reason |
|---|---|---|
| Note title | The file name stem. Not the H1, not a frontmatter key. | The design says the file name is the human title. |
| Note identity in the API | Vault-relative path. Lookup by frontmatter `id` is also offered (C21). Database primary keys are never exposed. | Paths and ids survive `reindex`; primary keys do not. |
| `id` value | Written as `{{date:YYYYMMDDHHmmss}}`, parsed by YAML as an integer, stored as a string in `note_id`. Within one operation that creates several notes, each gets a distinct id by advancing one second per note (C20). | Obsidian's core Templates can generate nothing else. |
| Renames | Delete plus add; logged as "moved" when the `id` matches (C21). | The index is keyed on path; nothing observable depends on more. |
| Frontmatter detection | File starts (after an optional BOM) with a line `---`; ends at the next line `---` or `...`. | Same as Obsidian. |
| Malformed frontmatter | Unterminated block, YAML syntax error, duplicate keys, or a non-mapping document (a list or a scalar): `parse_error` set, `frontmatter = {}`, body is the whole file, `type = note`. A file that is not valid UTF-8 is malformed too (`parse_error` names the first bad byte; the text is decoded with replacement characters so links and tags in it are still found), which also keeps the writer from editing it. An empty block (`---` directly followed by `---`, or holding only comments or blank lines) is **not** malformed: it is valid frontmatter with no keys, as in Obsidian after every property is deleted, so `parse_error` is not set, `type = note` and the body starts after the closing line. An unquoted value the YAML library cannot load as its implied type (for example `due: 2026-13-01`) is an invalid value under section 2.10, not malformed frontmatter: the other keys are kept. | Indexed, flagged, never fatal (design). |
| Promoted fields | `type`, `status`, `priority`, `project` (slug), `due`, `created`; how `type`, tags and dates are read is fixed in section 2.10. An unparseable date leaves the column null; the raw value stays in `frontmatter`, and the Index Status page lists such notes as "invalid dates" (computed, no extra column). | Only fields the UI filters on are promoted (design F). |
| Tags | Frontmatter `tags` plus inline tags, per section 2.10. | Matches Obsidian's tag pane. |
| Ignore rules | Any path segment starting with `.` (covers `.obsidian`, `.git`, `.trash`, temp files), `08-System/Templates/`, non-`.md` files, plus patterns in `<vault>/.sbignore` (one vault-relative glob per line, `#` comments, trailing `/` means a directory). `.sbignore` dialect: UTF-8 with an optional BOM, LF or CRLF; each line is trimmed; blank lines and lines starting with `#` are skipped; a pattern is matched against the whole vault-relative path with `/` separators, anchored at the vault root, case-insensitively, where `*`, `?` and `[seq]` are shell wildcards and `*` also matches `/`; a pattern ending in `/` ignores everything under any directory it matches, and a pattern without a trailing `/` never ignores a directory's contents; there is no `**`, no `!` negation and no escaping. A note is a regular file whose name ends in `.md` in any letter case; a symlink is never a note and a symlinked directory is never entered, so nothing outside the vault is read. Folder names and template file names are compared case-insensitively, because the vault's drive is case-insensitive. One shared implementation serves the checker, the indexer and the writer. | Design "Ignored paths"; dot-prefixed so Obsidian hides it. |
| Template source at runtime | The vault's `08-System/Templates/`, for the writer **and** the commands (review S-13). The copy shipped in the skill is only the seed used by the vault init script. | A template edited in Obsidian changes all three creators equally. |
| Writer temp file | `.<stem>.sbw-tmp-<8 random hex>` in the target directory. | Dot-prefixed and not ending in `.md`, per the design. |
| Vault path for commands | `$SECOND_BRAIN_VAULT` if set, else `/mnt/d/Second Brain`. | Lets every command test run against a temporary vault. |
| Container user | Backend and indexer run as uid:gid `1000:1000` unless the spike shows otherwise. | Files created through the mount stay editable by the WSL user and Obsidian. |
| App user (C18) | One Django user created by hand with `manage.py createsuperuser`, re-created by hand after any database rebuild. No credentials in `.env`. Tests and the e2e stack create their own users (section 6). | User's decision; the design records it as a deliberate exception to "the database holds no state of its own". |
| Secret key guard | Settings refuse to load when `DJANGO_SECRET_KEY` is missing or equals the `.env.example` placeholder. | A copied example file must not run with a known key. |
| `reindex` scope | Truncates `Note`, `Link`, `Tag` and the note-tag join table only, by explicit table names, never with `CASCADE`. User and session tables are untouched. | The user account survives an index rebuild. |
| List ordering | Every ordering ends with `path` as the final tiebreaker. | Deterministic output for the rebuild invariant (review S-7). |
| Index status | A dedicated Index Status page (C24); the Dashboard shows a small summary linking to it. | User's decision. |

### 2.10 Parsing details: types, tags and dates

These rules live in `backend/vault/parser.py` (P1-07) and are restated in the
skill's `reference/conventions.md` for the commands.

**`type`**

| Frontmatter | Indexed `type` |
|---|---|
| No frontmatter, malformed frontmatter, no `type` key, or `type` null, empty, or not a string | `note` |
| A string | The string trimmed and lower-cased (`Task ` → `task`). Known types get their vocabulary (section 2.3); any other value is kept as written, never mapped to `note`. |

Reason: keeping an unknown type visible lets the user find and fix it on the
Index Status counts by type; folding it into `note` would hide it.

**Tags**

- **Inline tags** are found in the body only, outside frontmatter, fenced code
  blocks, inline code spans and **the whole text of every wikilink and embed**
  (`[[...]]`, `![[...]]`). So `[[A#Heading]]`, `[[A#^block]]` and `[[#H]]`
  never produce tags.
- An inline tag is `#` that is at the start of a line or directly preceded by
  whitespace, followed by one or more **tag characters**: Unicode letters
  (categories L*), combining marks (M*, so that scripts such as Devanagari keep
  whole words), decimal digits (Nd), `_`, `-` and `/`. It ends at the first other character. So
  `# Heading` (space after `#`), `a#b` and `http://x/#frag` are not tags.
- A token is a tag only if it contains **at least one character that is not a
  digit and not `/`**. `#1984` and `#2026/10` are not tags; `#y1984` and
  `#v2` are. Reason: Obsidian requires a non-numerical character.
- **Nested tags**: `/` is kept as part of the tag (`#eng/backend` is stored as
  `eng/backend`); parents are not added as separate tags. Every trailing `/` is
  stripped (`#eng/` and `#eng//` → `eng`).
- **Frontmatter `tags`**: a YAML list (each item converted to a string) or a
  single string split on commas. Each item is trimmed, one leading `#` is
  removed, and the result must be a valid tag token as above (so an item with
  internal whitespace or a numeric-only item such as `2024` is dropped). Only
  the `tags` key is read.
- **Case and normalisation**: every tag is NFC-normalised and lower-cased;
  `#Eng` and `#eng` are one tag. Each note's tag set is de-duplicated.

Reason: these are Obsidian's own tag rules in the form that a regex and a
prose description both implement identically.

**Code regions** (used for links, tags and the writer's heading search alike,
through one shared function): a fenced code block opens on a line whose first
non-blank characters are three or more backticks or tildes, at any
indentation of spaces or tabs (so a fence inside a list item counts) and after
any blockquote markers (`>`, each optionally followed by a space, so a fence
inside a quote or an Obsidian callout counts), and,
for a backtick fence, has no further backtick on that line (so a line that
merely starts with an inline span such as ```` ```code``` and more ```` is
not a fence); it
closes on a later line that starts, after any indentation and blockquote
markers, with at least as
many of the same character and nothing else but whitespace; an unclosed fence
runs to the end of the file. Inline code spans are backtick runs matched by a
run of equal length and do not cross a blank line. Indented code blocks
without a fence are not code regions.

**Values the index must be able to store.** `frontmatter` is stored as JSON,
so the parser returns it JSON-safe: dates and timestamps as their text as
written, non-finite numbers (`.nan`, `.inf`) as their YAML text, and every
string an exact `str`. A NUL character or an unpaired surrogate (U+D800 to
U+DFFF) anywhere in the file, or in any decoded frontmatter key or value (a
YAML escape such as `"\0"` or `"\ud800"` can produce one from clean bytes),
makes the note malformed, like invalid UTF-8, with the character replaced,
because PostgreSQL cannot store either. A scalar the YAML library cannot load
as its implied type for any other reason (for example an integer of several
thousand digits) is kept as its text and the other keys are kept, like an
impossible date. A scalar explicitly tagged `!!str` is a string for every
rule (so `due: !!str 2026-10-09` is a valid date). An empty `id` is treated as no
id.


**Dates** (`due`, `created`, `decided`)

- Valid: a YAML date (`2026-10-09`); a YAML timestamp, whose calendar date as
  written is used with no timezone conversion; or a string that is exactly
  `YYYY-MM-DD` and a real calendar date.
- Anything else (for example `next week`, `2026-13-01`, `10/09/2026`, a
  number) is **invalid**: the promoted column is null, the raw value stays in
  `frontmatter`, and the note is listed under "invalid dates".
- An invalid `due` behaves exactly like no due date everywhere: excluded from
  `overdue`, from "due today", from `due_before`/`due_after` filters, sorted
  with "no due" (last), and not carried forward (section 2.2).

Dates given to a command or the API (`/task ... due:<date>`, the create
endpoint): the value written is always `YYYY-MM-DD`. A command accepts that
form as given. A relative expression (`tomorrow`, `friday`, `next week`) is
resolved by the command against today's date from section 2.12, written as
`YYYY-MM-DD`, and reported back in the command's output; `friday` means the
next Friday strictly after today. An expression with more than one reasonable
reading is not guessed: the command asks. The API accepts only `YYYY-MM-DD`
and returns `400` for anything else.

Reason: a date the system cannot read must never create or hide a deadline;
flagging it is the safe outcome.

### 2.11 Conformance checker rules

The checker (P1-08) reports **failures** (exit code 1) and **warnings** (printed,
exit code 0). Ignored paths (section 2.9) are not checked. Notes without
frontmatter, with empty frontmatter, with no usable string `type`, or with a
type outside the six known ones, are checked for failures F1 and F5 only; of
the warnings, only W4 can apply to them, and only when `type` is a string
outside the six known values (a non-string `type` such as `42` is indexed as
`note` and gets no W4).

Details the codes rely on. F2: a required key that is absent or null; an
empty string is present (so `status: ''` is F3, not F2, and `created: ''` is
F7). F3: `status` is compared exactly, with no trimming or case folding. F4:
"under" a folder includes its subfolders but not a sibling whose name merely
starts the same (`02-Work/TasksArchive/` is not under `02-Work/Tasks/`); a
daily note must be exactly `01-Daily/YYYY/YYYY-MM-DD.md`, a real calendar
date whose year equals the folder. F5: the file name only, against the
sanitising character sets and reserved device names; folder names, trailing
dots or spaces and the length limits are the writer's rules and are not
checked. F6: one line per missing template, at the template's own path. F8:
`priority` that is present, not null and either not a scalar or not one of
the three values. W2: ids are counted across every non-ignored note, and the
warning is reported on each note that is eligible for warnings.

Running: a note that disappears between listing and reading is skipped. A file
that cannot be read for another reason (permissions), or a `.sbignore` that
cannot be read, stops the run with exit code 2 and a message. Paths and
messages are printed on one line each, with control characters and bytes that
are not valid text escaped.

Unusable values: a `status` that is present and not null but is not a scalar
(a list or mapping) is F3. A `project` that is present and not null but
yields no slug (a list, a mapping, or text that slugifies to nothing) is W5.
The parser reports both states so the checker does not re-derive them.

Output: one line per note and code, `<code> <vault-relative path>: <message>`,
sorted by path then code. Several problems with the same code in one note
(for example two dropped tag items) are one line whose message lists them.

Required keys per type (present and not null):

| Type | Required keys |
|---|---|
| `task`, `project`, `decision`, `lesson`, `capture` | `type`, `status`, `created` |
| `daily` | `type`, `created` |

| Code | Failure | Code | Warning |
|---|---|---|---|
| F1 | Malformed frontmatter (any `parse_error` case of section 2.9) | W1 | Missing `id` |
| F2 | A known type missing a required key | W2 | Duplicate `id` |
| F3 | `status` outside the type's vocabulary (section 2.3) | W3 | A `project` or `triaged_to` wikilink (a string value or a list item) that resolves as ambiguous under section 2.8, that is to more than one note. A bare link to a duplicated stem is the usual case; a folder-qualified link that matches exactly one note is never W3, and a partly qualified one that still matches several is |
| F4 | A known type outside its folder: `task` must be under `02-Work/Tasks/`, `project` under `02-Work/Projects/`, `decision` under `05-Knowledge/Decisions/`, `lesson` under `05-Knowledge/Lessons/`, `capture` under `00-Inbox/`, and a `daily` note at `01-Daily/YYYY/YYYY-MM-DD.md` with matching year | W4 | Unknown `type` value: a string other than the six known types and other than `note` (an explicit `type: note` is the generic type, not unknown) |
| F5 | A file name containing a character from the sanitising sets, or a reserved device name (section 2.5) | W5 | `project` value that resolves to no project note, or to a duplicated project slug |
| F6 | One of the six templates missing from `08-System/Templates/` | W6 | A frontmatter `tags` item dropped as invalid (section 2.10) |
| F7 | An invalid date in `created`, `due` or `decided` (section 2.10) | | |
| F8 | `priority` present, not null, and not `low`, `medium` or `high` | | |

Reason: failures are things the system's own writers must never produce and a
user should fix; warnings are states the design explicitly tolerates (missing
and duplicate ids, unresolved links) or that can arise later without anyone
writing a bad note.

### 2.12 Test clock

One override pins "today" for tests; it is honoured identically by the
commands, the backend and the e2e stack.

- **Variables:** `SECOND_BRAIN_TODAY=YYYY-MM-DD` takes effect **only** when
  `SECOND_BRAIN_TEST_MODE=1` is also set. Either one alone is ignored (the
  backend logs a warning if only one is set).
- **Guards:** in test mode the commands refuse to run unless
  `SECOND_BRAIN_VAULT` is set and does not resolve to `/mnt/d/Second Brain`.
  Code compares resolved paths. A command session runs
  `[ "$SECOND_BRAIN_VAULT" -ef "/mnt/d/Second Brain" ]` and stops if it is
  true: `-ef` compares the directories themselves, so a different letter
  case, a dot segment, a doubled slash or a symlink anywhere in the path cannot
  pass. A `SECOND_BRAIN_TODAY` that is not a valid `YYYY-MM-DD` date also stops
  the command.
  The backend logs a warning at startup and reports `test_mode: true` and the
  pinned date in `/api/index/status/`. `scripts/check_compose.sh` fails if
  `.env` or `.env.example` sets either variable; only `.env.e2e` and the test
  harness set them.
- **Who uses it:** the command harness (P1-10) sets both, with the fixture's
  reference date `2026-10-09`; the backend `test` service and the `sbw-e2e`
  project set both; the real stack never does.
- **Time of day:** only the date is pinned. Outside test mode, an operation
  that needs a time of day (for an `id` or a capture name) reads
  `TZ=Asia/Manila date +%Y%m%d%H%M%S` once and takes both the date and the time
  from that single value, so the two cannot straddle midnight; the
  `date +%F` form in the skill wording below is for operations that need only
  the date. In test mode the date part is always `SECOND_BRAIN_TODAY` and only
  the time of day comes from the real clock (`TZ=Asia/Manila date +%H%M%S`,
  read once; the backend uses the current time in `TIME_ZONE`). The one-second
  advance per extra note (C20) changes the time part only and wraps within the
  day, so an `id` written in test mode always starts with the pinned date.
  Tests match it with a pattern (`^YYYYMMDD[0-9]{6}$` for the pinned date),
  never an exact value.
- **Backend:** one function, `vault.clock.today()`, returns the pinned date in
  test mode and otherwise the current date in `TIME_ZONE`. Every "today",
  "overdue" and daily-note computation calls it; pytest tests may also inject a
  date directly.
- **Checker:** it has no check that depends on today, so it reads neither
  variable.
- **Skill wording** (P1-03, `SKILL.md` and `reference/carry-forward.md`):
  "To get today's date, run `printenv SECOND_BRAIN_TEST_MODE SECOND_BRAIN_TODAY`.
  If `SECOND_BRAIN_TEST_MODE` is exactly `1` and `SECOND_BRAIN_TODAY` is set,
  today is `SECOND_BRAIN_TODAY`; in that case stop unless `SECOND_BRAIN_VAULT`
  is set and is not `/mnt/d/Second Brain`. Otherwise run
  `TZ=Asia/Manila date +%F`."

Reason: requiring two explicitly named variables, refusing the real vault in
test mode and keeping them out of `.env` makes an accidental pinned date in real
use practically impossible, while one mechanism serves code and prose alike.

### 2.13 Triage rules

Confirmed by the user on 2026-10-05. `/triage` and `POST /api/captures/triage/`
follow them.

Each inbox capture gets one `classification`, written as a lower-case
frontmatter value: one of the brief's nine kinds (section 23), or `project`
for a capture that describes a new body of work. That is ten allowed values:

| `classification` | Phase 1 result |
|---|---|
| `task`, `problem` | a `task` note |
| `decision` | a `decision` note |
| `learning-topic`, `note` | a `lesson` note |
| `project` (a new body of work) | a `project` note |
| `ticket`, `architecture-idea`, `question`, `thought` | no target note in Phase 1: the capture stays in `00-Inbox/` with `status: inbox` and its `classification`, until the phase that owns that kind exists |

Confidence:

- **High confidence** means the capture states its own kind (for example it
  starts with `task:`, `todo:`, `decision:` or "decided to ...") or it is a
  plain imperative with one obvious reading ("Renew the domain"). Only then is
  `classification` written without asking.
- **Anything else** is low confidence: nothing is written; the command shows
  its suggested classification for the user to accept or change.

Flow: turn 1 writes `classification` on high-confidence captures only and
shows one batch listing, per capture, the classification and the note it would
create (or "stays in inbox"), with low-confidence suggestions marked. After the
user's approval, with any changes they made, it creates the target notes
(target first, section 4), then sets `status: triaged` and `triaged_to` on each
converted capture. A capture the user dismisses gets `status: dismissed`.
Captures are never moved or deleted. A capture whose classification has no
Phase 1 target is not converted and is not offered again as a conversion in
later runs, only listed.

Reason: the mapping uses only the four note types Phase 1 has; kinds owned by
later phases are kept, labelled, where the user will find them, and nothing is
filed on a guess.

---

## 3. Templates

### 3.1 Placeholder subset

Verified against Obsidian's Templates documentation (section 13): the core
plugin supports `{{title}}`, `{{date}}` (default `YYYY-MM-DD`), `{{time}}`
(default `HH:mm`), and `{{date:FORMAT}}` / `{{time:FORMAT}}` with Moment.js
format tokens.

The templates use only `{{title}}`, `{{date:YYYY-MM-DD}}` and
`{{date:YYYYMMDDHHmmss}}`. The writer and the commands implement exactly
`{{title}}`, `{{date}}`, `{{time}}`, `{{date:F}}` and `{{time:F}}` where `F`
contains only the tokens `YYYY`, `MM`, `DD`, `HH`, `mm`, `ss` and literal
non-letter characters. Any other token is a template error.

### 3.2 Template content

Stored in the vault at `08-System/Templates/<name>.md`, seeded from
`claude/skills/second-brain/templates/`. Each file is shown exactly. A key with
no value is YAML null; `tags: []` is an empty list.

**`task.md`**

```markdown
---
type: task
id: {{date:YYYYMMDDHHmmss}}
status: planned
priority: medium
project:
created: {{date:YYYY-MM-DD}}
due:
tags: []
---

## Description

## Notes

## Links
```

**`project.md`**

```markdown
---
type: project
id: {{date:YYYYMMDDHHmmss}}
status: active
created: {{date:YYYY-MM-DD}}
tags: []
---

## Goal

## Scope

## Notes

## Links
```

**`daily.md`**

```markdown
---
type: daily
id: {{date:YYYYMMDDHHmmss}}
created: {{date:YYYY-MM-DD}}
tags: []
---
# Standup - {{title}}

## Done

## Today

## Blockers

## Decisions / Updates

## Follow-ups

## Related Tasks / Projects
```

`{{title}}` rather than `{{date}}` in the heading, because the title of a daily
note is its date.

**`decision.md`**

```markdown
---
type: decision
id: {{date:YYYYMMDDHHmmss}}
status: proposed
project:
created: {{date:YYYY-MM-DD}}
decided:
tags: []
---

## Context

## Options considered

## Decision

## Consequences

## Links
```

**`lesson.md`**

```markdown
---
type: lesson
id: {{date:YYYYMMDDHHmmss}}
status: active
project:
created: {{date:YYYY-MM-DD}}
tags: []
---

## Context

## What happened

## Lesson

## Apply next time

## Links
```

**`capture.md`**

```markdown
---
type: capture
id: {{date:YYYYMMDDHHmmss}}
status: inbox
created: {{date:YYYY-MM-DD}}
tags: []
---

```

The captured text is the body. Triage adds `classification:` (one of
`thought`, `task`, `ticket`, `architecture-idea`, `learning-topic`,
`decision`, `question`, `note`, `problem`, the brief's section 23 list, or
`project`; see section 2.13) and, when converted, `triaged_to: "[[Target note]]"`.

Keys set by tools only when needed: `project` (as a wikilink, section 2.1),
`blocked_by` (task), `decided` (decision, set when status becomes `accepted`),
`classification` and `triaged_to` (capture). When a task is marked `done` with
evidence, the evidence is appended under `## Notes`.

### 3.3 Obsidian settings for the vault

Set by the user in P1-05 and committed with `.obsidian/`:

| Setting | Value |
|---|---|
| Core plugin Templates: folder | `08-System/Templates` |
| Core plugin Daily notes: folder / format / template | `01-Daily` / `YYYY/YYYY-MM-DD` / `08-System/Templates/daily` (the resulting untouched note is filled by carry-forward, section 2.2) |
| Files and links: Use `[[Wikilinks]]` | On |
| Files and links: New link format | Shortest path when possible |
| Files and links: Automatically update internal links | On (keeps wikilink-valued `project` keys correct on rename) |
| Files and links: Default location for new notes | `00-Inbox` |
| Property types (if Obsidian infers otherwise) | `id`: text; `created`, `due`, `decided`: date |
| Obsidian Sync | Off (C14) |

---

## 4. Command contracts

Each command is a thin Markdown file that loads the `second-brain` skill; the
skill holds the vault path rule, conventions, the template rendering subset and
the shared algorithms (sanitising, emitted links, carry-forward, triage
mapping). Commands read and write the vault with Claude Code's own file tools
and read templates from the vault's `08-System/Templates/` (section 2.9). The
install script refuses to overwrite any existing file it did not install, and
P1-15 confirms each name resolves to this project's command.

| Command | Arguments | Writes | Asks the user before |
|---|---|---|---|
| `/capture` | free text | one new `capture` note in `00-Inbox/` | nothing |
| `/triage` | none | sets `classification` on captures at high confidence; after approval, creates target notes (target first) and then sets capture `status: triaged` + `triaged_to`, or `dismissed` | creating any target note or dismissing (one batch confirmation; low-confidence items are only suggested) |
| `/task` | `<title> [project:<slug or title>] [due:<date>] [priority:<p>]`, or `<title or path> status:<status>` | a new `task` note, or a status change | marking `done` (asks for evidence and records it under `## Notes`) |
| `/project` | `<title>`, or `<slug>` to show a summary | a new `project` note | nothing; refuses on slug clash |
| `/decision` | `<title> [project:<slug or title>]` | a new `decision` note | nothing |
| `/knowledge` | `<title> [project:<slug or title>]` | a new `lesson` note in `05-Knowledge/Lessons/` | nothing |
| `/daily` | none | today's daily note with carry-forward if it does not exist or is untouched | nothing |
| `/standup` | optional free text | ensures today's note (as `/daily`), fills sections from the user's input, prints the standup text ready to paste | any status change it infers |
| `/eod` | optional free text | appends to today's `## Done`; offers status changes for `in-progress` tasks; then commits the vault through `vault_git.py` (section 4.2) | each status change; stops if `vault_git.py` refuses, including when its secret scan matches |

### 4.1 Command details

Settled on 2026-10-05 after the command-test and security reviews.

- **Git is written only by the init script and `/eod`** (section 2.6). No other
  command stages, commits or changes git configuration; the command tests
  assert `HEAD` and the index are unchanged after every other command.
- **Created notes:** keys the user did not give keep the template's values;
  `project:` stays empty unless a project was given.
- **`/task`:** a resolved relative due date is reported back in the reply
  (section 2.10). Marking a task `done` asks for evidence first.
- **`/project <argument>`:** if the argument is exactly the slug of an existing
  project note (`harbor-lights`), the command shows that project's summary and
  writes nothing. Otherwise, if the argument's slug equals an existing
  project's slug (`Harbor Lights!`), it refuses and names the existing note.
  Otherwise it creates the project note.
- **`/triage`:** a capture that is a question (its first sentence ends with `?`) states its
  own kind and is high confidence, classified `question`. A converted
  capture's target title is the capture's text, sanitised (section 2.5),
  unless the user gives another. Answering "no" changes nothing beyond the
  classifications turn 1 already wrote.
- **`/standup`:** input labelled `Done:`, `Today:`, `Blockers:`, `Decisions:`
  or `Follow-ups:` goes under that heading; unlabelled input is placed by its
  meaning, and the command asks when that is unclear. The standup text is
  printed in the same turn, before any question. `/standup` never ticks or
  removes a carried-forward item and never changes a task without asking.
- **`/eod`, in order:** (1) refuse, before writing anything, if the vault has a
  git remote; (2) ensure today's daily note exists, as `/daily` does; (3)
  append the user's text to `## Done`, leaving every other section unchanged;
  (4) list the `in-progress` tasks by title and offer a status change for
  each, asking before any change; (5) apply the answers; (6) run
  `vault_git.py commit-eod <today>`, which stages, scans and commits. Step 1
  uses the `remote` verb; the script's own refusal of a vault with a remote
  is the backstop if the session misreads it. `status`, `stage`,
  `staged-diff` and `head-subject` are there for a session to show the user
  what will be committed; `/eod` does not need them.

### 4.2 `vault_git.py`: the only way a command runs git

A session never runs `git` directly. The skill ships
`skills/second-brain/scripts/vault_git.py` (Python standard library only),
and `/eod` calls `python3 -I <skill directory>/scripts/vault_git.py <verb>`
(`-I` is Python's isolated mode: it ignores `PYTHONPATH` and the other
`PYTHON*` variables and the user site directory, which would otherwise act
before the script's first line).
Reason: a permission rule that allows `git` allows any repository, any
configuration and any program git can launch (demonstrated in the security
review of the command tests), so the allowed surface is a fixed script with
fixed verbs, and the same protection applies to the real vault.

| Verb | Does |
|---|---|
| `remote` | prints the configured remotes, one per line (nothing means none) |
| `status` | prints `git status --porcelain` |
| `stage` | `git add -A` |
| `staged-diff` | prints the names of staged files and the staged diff |
| `head-subject` | prints the subject of `HEAD`, or nothing when there is no commit |
| `commit-eod YYYY-MM-DD` | stages every change (as `stage` does), scans the staged diff, then commits with the message `eod: YYYY-MM-DD`; if `HEAD`'s subject is already exactly that, amends it instead, so there is one commit per day. With nothing to commit it says so and changes nothing |

Rules the script enforces itself, whatever the caller says:

- The vault is `SECOND_BRAIN_VAULT` if set, else `/mnt/d/Second Brain`. It
  must be a directory that is the root of a git work tree; nothing else is
  ever passed to git, and no verb takes a path.
- The test-clock guard of section 2.12: with `SECOND_BRAIN_TEST_MODE=1` it
  refuses unless `SECOND_BRAIN_VAULT` is set and is not the real vault.
- Every git call uses the vault as its directory, drops every `GIT_*`
  variable from the environment, sets `GIT_CONFIG_NOSYSTEM=1`,
  `GIT_CONFIG_GLOBAL=/dev/null` and an empty `GIT_ALLOW_PROTOCOL` (no
  transport works), and pins `core.hooksPath=/dev/null`,
  `core.fsmonitor=false`, `core.pager=cat`, `core.sshCommand=false` and
  `credential.helper=` on the command line. It never pushes, fetches, adds a
  remote or writes git configuration.
- `commit-eod` refuses when a remote is configured, when the date is not a
  real `YYYY-MM-DD` date, and when the secret scan matches. The scan covers
  added lines of the staged diff: private key headers, `password`, `token`,
  `secret` or `api key` followed by `:` or `=` and a non-empty value, and
  common token prefixes (`ghp_`, `github_pat_`, `glpat-`, `sk-`, `xox`,
  `AKIA`). On a match it prints the file name and the kind of match, never
  the matched text, and exits non-zero without committing.
- Exit code 0 on success, 1 on a refusal with a one-line reason, 2 on a usage
  error.

---

## 5. API surface

All paths are under `/api/`, reached from the browser only through the Vite
proxy at `http://localhost:5173`. Session authentication with CSRF enforced on
every unsafe method. "Session" means an authenticated session is required. The
OpenAPI schema (`backend/openapi.yaml`) is produced in P1-24 and is the
contract.

| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | `/api/health/` | Liveness and database reachability; returns `{"status": "ok"}` and nothing else | none |
| GET | `/api/auth/csrf/` | Sets the CSRF cookie | none |
| POST | `/api/auth/login/` | Session login (`username`, `password`); throttled to 5 per minute | none, CSRF required |
| POST | `/api/auth/logout/` | End the session | session |
| GET | `/api/auth/me/` | Current user name | session |
| GET | `/api/notes/` | List notes. Filters: `type`, `status` (repeatable), `priority`, `project` (slug), `tag`, `due_before`, `due_after`, `overdue`, `path_prefix`, `has_parse_error`. Ordering: `-modified` (default), `due`, `title`, `path`; every ordering ends with `path`. Paginated. | session |
| GET | `/api/notes/lookup/?path=` or `?id=` | One note: promoted fields, `frontmatter`, `body`, `content_hash`, `modified`, `parse_error`, backlinks, and `links`: a map from each link target as written to `{path, state}` with state `resolved`, `ambiguous` or `unresolved` (review O-7). `?id=` matching several notes returns `409` with the candidate paths. | session |
| POST | `/api/notes/` | Create from template (C17): `type` in `task`, `project`, `decision`, `lesson`; `title`; optional `project` (slug or title), `priority`, `due`, `status`, `body`. Returns the indexed note (`201`); `409` on same-folder collision; `422` for an unknown project. | session |
| POST | `/api/notes/status/` | Change status (C17): `path`, `status`, `expected_hash`, optional `evidence` (appended under `## Notes` when the status becomes `done`). Validates the per-type vocabulary. `409` on hash mismatch, `422` on malformed frontmatter. | session |
| POST | `/api/captures/` | Quick capture: `text`. Creates a `capture` note | session |
| POST | `/api/captures/triage/` | (C17) `path`, `expected_hash`, `action` (`task`, `decision`, `lesson`, `project`, `keep`, `dismiss`), `classification`, optional `title`, `project`, `existing_target`. Writes the target note first, then edits the capture. If the capture edit fails, the response is the error plus `created_target` (the new note's path). A retry with `existing_target` set to that path skips creation, passes the path through the writer's path confinement (vault-relative, not in an ignored folder, `.md`; otherwise `400`), then checks the target exists on disk, and only edits the capture. | session |
| GET | `/api/projects/` | Project notes with slug, status and open-task count | session |
| GET | `/api/projects/{slug}/` | One project: note, open tasks, decisions, recent notes (by modified time, then path) | session |
| GET | `/api/standups/today/` | Today's daily note with `untouched: true/false`, or `404` with a carry-forward preview | session |
| POST | `/api/standups/today/` | Runs one sync pass under the advisory lock, then: creates today's note with carry-forward (`201`), fills it if untouched (`200`, `filled: true`), or returns it unchanged if touched (`200`, `filled: false`) | session |
| POST | `/api/standups/today/append/` | `section` (one of the six headings), `text`, `expected_hash`. Appends to today's note | session |
| GET | `/api/dashboard/` | Aggregates: today's tasks, in progress, blocked, overdue, today's standup, recent activity, active projects, inbox count, and a small index status summary (last pass time, problem count) | session |
| GET | `/api/search/?q=` | Full-text search (`simple` configuration) plus trigram title match; each result has `path`, `type`, `title`, `snippet`, `source: "vault"`; ties ordered by `path` | session |
| GET | `/api/index/status/` | For the Index Status page: last pass time and duration, note counts by type, parse errors, missing ids, duplicate ids, ambiguous links, unknown and duplicate project slugs, unknown statuses, invalid dates, and `test_mode` with the pinned date when section 2.12 test mode is on | session |
| POST | `/api/index/refresh/` | Run one sync pass now and return its summary | session |
| GET | `/api/schema/` | The OpenAPI document | session |

Rebuild invariant (P1-21 at model level, P1-30 at API level): after `reindex`
from an empty index, every read endpoint above returns identical responses for
the same vault, excluding only the timing fields of `/api/index/status/` and of
the dashboard's index summary.

Daily notes are listed with `GET /api/notes/?type=daily&ordering=-path`; no
separate list endpoint.

---

## 6. Repository layout and Compose

```text
second-brain-workflow/
├── AGENTS.md  CLAUDE.md  README.md             README written in P1-40
├── .env.example  .env.e2e.example  .gitignore
├── docker-compose.yml                          db, backend, indexer, frontend; profiles "test", "e2e"
├── docs/
│   ├── plan/  specs/
│   └── spikes/                                 P1-02 and P1-05 results
├── scripts/
│   ├── spike/                                  mount spike (P1-02)
│   ├── check_compose.sh                        P1-16
│   ├── e2e.sh                                  e2e stack up/down/user (P1-19)
│   ├── check_csrf_proxy.sh                     P1-31
│   └── check_readme.sh                         P1-40
├── fixtures/
│   └── golden-vault/
│       ├── README.md                           what each sample note exercises
│       ├── vault/                              the sample vault (incl. .obsidian/, 08-System/Templates/)
│       └── expected/
│           ├── index.json                      expected parse result per note
│           └── carry-forward/{new-note,untouched-note}/
├── claude/
│   ├── pyproject.toml  uv.lock                 test deps for claude/ tooling (pytest, ruamel.yaml)
│   ├── install.sh                              install / --uninstall / --target DIR / --dry-run
│   ├── skills/second-brain/
│   │   ├── SKILL.md
│   │   ├── reference/                          conventions, naming, links, carry-forward, triage, templates
│   │   ├── templates/                          the six seed templates (section 3.2)
│   │   └── vault-readme.md                     copied to the vault as README.md
│   ├── commands/                               capture triage task project daily standup eod decision knowledge (.md)
│   ├── scripts/init_vault.py                   vault init (P1-04)
│   └── tests/                                  templates, skill, init, install; commands/ (headless scenarios)
├── backend/
│   ├── Dockerfile  pyproject.toml  uv.lock  manage.py
│   ├── openapi.yaml                            committed contract (P1-24)
│   ├── config/                                 settings (from env), urls, wsgi
│   ├── vault/
│   │   ├── parser.py links.py slug.py conventions.py   pure Python, no Django imports (P1-07)
│   │   ├── conformance.py                      vault checker CLI over the parser (P1-08)
│   │   ├── models.py indexer.py queries.py
│   │   ├── sanitize.py templating.py writer.py carry_forward.py clock.py
│   │   └── management/commands/                sync_vault, reindex
│   ├── api/                                    serializers, views, urls, auth, permissions
│   └── tests/
└── frontend/
    ├── Dockerfile  package.json  package-lock.json
    ├── vite.config.ts  vitest.config.ts  eslint.config.js  tsconfig*.json  components.json
    ├── src/
    │   ├── api/                                client, types generated from openapi.yaml
    │   ├── components/ui/                      shadcn/ui components
    │   ├── components/                         shared (NoteReader, StatusBadge, QuickActions)
    │   ├── features/<page>/                    dashboard tasks inbox standups projects knowledge search index-status
    │   └── routes.tsx  main.tsx
    ├── e2e/                                    Playwright specs and config
    └── tests/                                  shared test setup
```

Compose services. Published ports use `${BACKEND_PORT:-8000}` and
`${FRONTEND_PORT:-5173}` so the e2e project can run beside the real stack.

| Service | Image | Mounts | Ports |
|---|---|---|---|
| `db` | `postgres:18` | named volume `pgdata` at `/var/lib/postgresql` (the 18+ layout) | none |
| `backend` | built from `backend/Dockerfile` (`python:3.12-slim` + uv) | `${VAULT_PATH}:/vault` rw, `./backend:/app` | `127.0.0.1:${BACKEND_PORT}:8000` |
| `indexer` | same image, `manage.py sync_vault --watch` | `${VAULT_PATH}:/vault:ro` | none |
| `frontend` | built from `frontend/Dockerfile` (`node:22-slim`); Vite listens on `0.0.0.0` inside the container | `./frontend:/app`, named volume `node_modules` | `127.0.0.1:${FRONTEND_PORT}:5173` |
| `test` (profile `test`) | backend image | `./backend:/app`, `./fixtures:/fixtures:ro`; **no vault mount** | none |
| `e2e` (profile `e2e`) | `mcr.microsoft.com/playwright:v1.63.0-noble` (same version as `@playwright/test`) | `./frontend:/app` | none; `network_mode: "service:frontend"` |

Per C23, the only host **data** path mounted is the vault; repository source and
read-only fixtures are mounted for development and tests.

### Test isolation

(Review M-3.)

- Backend tests run only in the `test` service. It has no `/vault` mount.
- Test settings set the vault root to a per-test temporary directory (a copy of
  the golden vault where needed).
- An autouse fixture fails the run if `/vault` exists in the container or if any
  code path resolves a path under it.
- Tests create their own Django user with pytest-django fixtures. No test reads
  user credentials from the environment.
- The real-vault rebuild comparison in P1-41 runs against a copy of the vault
  made by `scripts/e2e.sh up --vault-copy-of`, in the e2e project, never
  through a writable test container and never against the real project's
  database.

### The e2e stack

(Review S-11.)

- A separate Compose project, `docker compose -p sbw-e2e --env-file .env.e2e`,
  with its own named volumes, its own database, `FRONTEND_PORT=5174`,
  `BACKEND_PORT=8001`, and `VAULT_PATH` pointing at a fresh copy of the golden
  vault under `/mnt/d/sbw-e2e/`.
- `scripts/e2e.sh up|user|down` creates the copy, starts the project, and
  creates the e2e user non-interactively with
  `createsuperuser --noinput` and `DJANGO_SUPERUSER_PASSWORD` supplied on that
  one command line. The script refuses to run unless the project name is
  `sbw-e2e`, and refuses if `VAULT_PATH` resolves to `/mnt/d/Second Brain`.
  This non-interactive step never applies to the real stack.
- `scripts/e2e.sh up --vault-copy-of <path>` is the mode for the final rebuild
  check: it copies `<path>` (which may be the real vault) to a fresh directory
  under `/mnt/d/sbw-e2e/`, excluding `.git/`, and mounts only that copy. The
  source path is read, never mounted; the same `VAULT_PATH` guard applies to
  the copy's resolved path. Without the flag, `up` copies the golden vault.

---

## 7. Pinned versions

"Checked" means confirmed in current documentation through context7 on
2026-10-05. "Judgment" means chosen without a documentation check; the
implementing task confirms it and records the exact version in the lock file.

| Component | Pin | Basis |
|---|---|---|
| Python | 3.12 (`python:3.12-slim`) | Judgment, matches WSL 3.12.3. Checked: Django 5.2 supports 3.10 to 3.14. |
| Django | **5.2 LTS** (`>=5.2,<5.3`) | Checked: DRF lists Django 5.2, 6.0, 6.1; pytest-django lists 5.2 and 6.1; drf-spectacular's README lists Django 3.2 to 6.0. 5.2 is the only series all three list, and it is LTS. |
| Django REST Framework | **3.17** (`>=3.17.2,<3.18`) | Checked: requires Python 3.10+, supports Django 5.2; 3.17.2 enforces `DATA_UPLOAD_MAX_MEMORY_SIZE` on JSON and form bodies (security fix). |
| drf-spectacular | latest 0.x, upper-bounded to the minor installed | Checked: supports DRF 3.12 to 3.17 and Django 3.2 to 6.0; `spectacular --file ... --validate --fail-on-warn`. Exact version number not checked. |
| psycopg | 3 (`psycopg[binary]>=3.2,<4`) | Checked: Django requires psycopg 3.1.12+; the 3.2 floor is judgment. |
| PostgreSQL image | **`postgres:18`** | Checked: stored generated `tsvector` columns, `pg_trgm` GIN; generated columns default to `VIRTUAL` in 18, so the search vector must be `STORED`; 18+ images keep data under `/var/lib/postgresql`. Not checked: Django 5.2 naming PostgreSQL 18 as supported. Fallback: `postgres:17` with the old volume path. |
| YAML round-trip | **ruamel.yaml 0.18** (`>=0.18,<0.19`) | Checked: round-trip mode preserves key order, comments and quoting; duplicate keys raise `DuplicateKeyError`. Docs reference 0.18.6; newer minors not checked. |
| pytest | 9 (`>=9,<10`) | Checked: pytest 9.0 exists; pytest-django requires pytest 7.0+. |
| pytest-django | 4.x latest | Checked: supports Django 5.2 and Python 3.10+. Exact version not checked. |
| ruff | latest, pinned in `uv.lock` | Judgment. |
| Node | **22 LTS** (`node:22-slim`, at least 22.12) | Checked: Vite 8 requires Node `^20.19.0 \|\| >=22.12.0`. WSL has 22.22.0. |
| Vite | **8** | Checked: `server.proxy`, `server.watch.usePolling` (documented as needed under WSL2 for Windows-edited files), `server.host`. |
| React | **19** | Checked: 19.2.x. |
| TypeScript | 5.x | Judgment. |
| Tailwind CSS | 4 via `@tailwindcss/vite` | Checked: shadcn/ui's Vite installation guide. |
| shadcn/ui CLI | `shadcn@latest` at init, components committed | Checked: `init -t vite` and options. |
| Vitest | **4** | Checked: 4.1.x; requires Vite 6+ and Node 20+. |
| React Testing Library, jsdom | latest | Judgment. |
| ESLint | latest flat config | Judgment. |
| openapi-typescript | latest | Judgment. |
| Playwright | **1.63** (`@playwright/test` and the image at the same version) | Checked: `webServer`, `baseURL`, setup project with `storageState`. Image tag format not checked. |

---

## 8. Mount spike procedure

Owner: P1-02. Runs only after P1-01. Uses a scratch folder, never the vault.

**Setup**

1. Scratch root: `/mnt/d/sbw-spike/Spike Vault` (the space is deliberate).
2. `scripts/spike/gen_corpus.py` creates 5,000 Markdown files of 1 to 4 KB,
   spread over 20 folders up to 3 levels deep, with frontmatter, including
   names with spaces and non-ASCII characters. Deterministic seed.
3. `scripts/spike/compose.spike.yml` defines two services from
   `python:3.12-slim`: `probe` (`${SPIKE_PATH}:/vault` read-write, user
   `1000:1000`) and `probe_ro` (`${SPIKE_PATH}:/vault:ro`). `SPIKE_PATH` comes
   from `scripts/spike/.env`.
4. `scripts/spike/measure.py` runs inside the container; subcommands below.
   `scripts/spike/run.sh` runs the automated measurements and writes a JSON
   result file. Manual steps are a checklist in the results document.

**Measurements and thresholds**

Timing results are recorded as milliseconds per file and projected to 1,000
and 5,000 notes (review S-10). Gating uses the 1,000-note projection; the
5,000-note projection is recorded as a risk.

| # | Measurement | How | Pass | Soft pass (adjust, continue) | Fail |
|---|---|---|---|---|---|
| M0 | Docker works in WSL | `docker compose version`; `docker run --rm hello-world` | both succeed | | either fails (back to P1-01) |
| M1 | Stat-only walk | `measure.py scan`: walk + `stat` all files; 1 cold + 5 warm runs; ms/file from the warm median | 1,000-note projection ≤ 3 s | ≤ 10 s (the poll interval): poll interval raised to 30 s | > 10 s |
| M2 | Full read + SHA-256 | `measure.py hash`; ms/file | 1,000-note projection ≤ 30 s | > 30 s: recorded, `reindex` is slower | none (informational) |
| M3 | Host edits visible | `measure.py watch` polls `(mtime_ns, size)` every 0.5 s while the operator makes 10 edits: 5 from WSL (`printf >>`), 5 in Obsidian on Windows | 10/10 seen within 2 s | seen within 10 s | any edit not seen after 10 s |
| M4 | mtime resolution | `measure.py mtime`: two writes 50 ms apart, compare `mtime_ns` | recorded | | informational; sets the racy window (section 2.7) |
| M5a | Atomic replace, file not open | `measure.py replace --n 100`: temp file `.x.sbw-tmp-*`, `fsync`, `os.replace` | 100/100, content correct | | any failure or partial content |
| M5b | Replace over a file open in Obsidian | operator opens the target in Obsidian (not typing), then `measure.py replace --target <file>` | replace succeeds; Obsidian shows new content within 5 s, no revert, no conflict dialog | Obsidian needs a click into the note to refresh | replace fails, or Obsidian writes old content back |
| M5c | Replace over a file locked by Windows | from WSL, `powershell.exe` opens the file with `FileShare.Read` only, then `measure.py replace` | the error surfaces as a Python exception | | silent success with wrong content |
| M6 | Temp file invisible | during M5b, operator checks Obsidian's file list and search | never shown | | shown |
| M7 | Ownership and permissions | `measure.py create`; in WSL `stat`, edit with `printf >>`, `git status` in a scratch repo with `core.filemode=false`; operator edits it in Obsidian | WSL user and Obsidian can edit without `sudo`; no mode-only diff | needs a different container uid: record it | not editable from Obsidian or WSL |
| M8 | Space in the path | `docker compose -f ... config` and a `probe` run with `SPIKE_PATH` unquoted, then quoted | at least one form mounts the right folder; record which | | neither works |
| M9 | Read-only mount | `probe_ro` attempts a write | fails with `EROFS` | | write succeeds |
| M10 | Case collisions | create `Case.md` then `case.md` | recorded | | informational; confirms section 2.5 |
| M11 | Illegal characters | try creating `a:b.md`, `a?b.md` | recorded | | informational; confirms section 2.5 |
| M12 | Steady-state cost | `measure.py poll --interval <chosen>` for 10 minutes over the 5,000-file corpus; `docker stats` sampled every 10 s | recorded: mean and peak CPU, block I/O | | informational; mean CPU above 10% of one core is recorded as a risk |

**Result.** `docs/spikes/phase-1-mount-spike.md` records each measurement, the
raw JSON, the projections, the chosen poll interval, racy window, container uid
and `.env` quoting form. The orchestrator reads it and marks Gate B open or not.

**If it fails.** Any Fail stops Gate B, as the master plan requires; the design
returns to planning and the vault stays on `D:`. Gate A (vault, commands,
fixture, parser, checker) continues unaffected. The replanning would weigh,
without this plan presupposing any of them: running `backend` and `indexer`
natively in WSL with only `db` and `frontend` in Compose; a longer poll interval
with on-demand refresh only; or a different mount mechanism. Soft passes change
the named parameter and are listed in the results document.

**Cleanup.** The operator deletes `/mnt/d/sbw-spike` after the results are
recorded.

---

## 9. Tasks

### Step 1: Prerequisites and mount spike

#### P1-01 Enable Docker in WSL

- **Goal:** make `docker` and `docker compose` usable inside this WSL distro.
- **Step:** 1. **Gate:** none.
- **Files:** none.
- **Depends on:** none.
- **Agent:** user, orchestrator verifies. **Reviewers:** none (no change to review).
- **Tests first / Run:** `docker compose version && docker run --rm hello-world`.
- **Acceptance:** both commands succeed in WSL; output pasted into the tracker issue.

#### P1-02 Mount spike

- **Goal:** measure the Windows bind mount against section 8 and record pass or fail.
- **Step:** 1. **Gate:** between A and B.
- **Files:** `scripts/spike/{gen_corpus.py,measure.py,run.sh,compose.spike.yml,.env.example}`, `docs/spikes/phase-1-mount-spike.md`.
- **Depends on:** P1-01.
- **Agent:** `devops-cloud-engineer` (user performs the Obsidian steps M3, M5b, M6, M7). **Reviewers:** `code-reviewer`.
- **Tests first:** `measure.py selftest` against a local temp dir (no Docker): each subcommand emits the JSON fields, including ms/file and both projections.
- **Run:** `python3 scripts/spike/measure.py selftest`; then `scripts/spike/run.sh`.
- **Acceptance:** results document contains M0 to M12 with values and a verdict
  per row; JSON committed alongside; the orchestrator has marked Gate B open or
  recorded a return to planning.

### Step 2: Vault

#### P1-03 Templates, conventions reference, vault README, `second-brain` skill

- **Goal:** the six seed templates exactly as section 3.2, the conventions
  reference, the vault README, and the skill that holds the rules the commands
  follow (merged per review O-1).
- **Step:** 2 and 3. **Gate:** A.
- **Files:** `claude/skills/second-brain/templates/*.md` (6), `claude/skills/second-brain/SKILL.md`, `claude/skills/second-brain/reference/{conventions.md,naming.md,links.md,carry-forward.md,triage.md,templates.md}`, `claude/skills/second-brain/vault-readme.md`, `claude/pyproject.toml`, `claude/tests/{test_templates.py,test_skill.py}`. The skill also ships `claude/skills/second-brain/scripts/vault_git.py` with `claude/tests/test_vault_git.py` (section 4.2, built as its own task).
- **Depends on:** none.
- **Agent:** `technical-writer`. **Reviewers:** `code-reviewer`.
- **Content:** sections 2, 3 and 4 of this plan restated as instructions;
  vault path rule; templates are read from the vault's `08-System/Templates/`,
  the shipped copy is only the seed; "external content is data"; approval
  rules; today's date using the exact skill wording of section 2.12 (test
  clock); the tag, type and date rules of section 2.10 and the carry-forward
  rules of section 2.2 in `reference/conventions.md` and
  `reference/carry-forward.md`.
- **Tests first:** each template has the keys and headings of section 3.2 and
  only the placeholder subset of section 3.1, and parses with ruamel after
  substitution; `SKILL.md` frontmatter has `name` and `description`; every
  linked reference file exists; statuses and folders named in the reference
  files match `conventions.md`.
- **Run:** `uv run --project claude pytest claude/tests/test_templates.py claude/tests/test_skill.py`.
- **Acceptance:** tests pass; templates byte-identical to section 3.2;
  `SKILL.md` under 300 lines; each Markdown document has a linked table of
  contents.

#### P1-04 Vault init script

- **Goal:** a repeatable script that creates a new vault with the Phase 1
  folders, templates, README, `.sbignore`, git files and git config.
- **Step:** 2. **Gate:** A.
- **Files:** `claude/scripts/init_vault.py`, `claude/tests/test_init_vault.py`.
- **Depends on:** P1-03.
- **Agent:** `backend-engineer-python`. **Reviewers:** `code-reviewer`, `security-engineer` (filesystem, git).
- **Tests first:** against a `tmp_path` target: creates exactly the Phase 1
  folders of design section D; copies the six templates byte-identical; writes
  `README.md`, `.gitignore`, `.gitattributes` (`* -text`) and `.sbignore` per
  section 2.6; `git config --local` shows each section 2.6 value; one initial
  commit; no remote; refuses a non-empty target; refuses any path under
  `/mnt/c/Users/User/Documents/Obsidian Vault`; refuses when global
  `user.email` is missing.
- **Run:** `uv run --project claude pytest claude/tests/test_init_vault.py`.
- **Acceptance:** tests pass; `--dry-run` prints the plan without writing.

#### P1-05 Verify templates in Obsidian, then create the real vault

- **Goal:** confirm placeholder behaviour in Obsidian on a scratch vault, then
  create `/mnt/d/Second Brain` with Obsidian Sync off.
- **Step:** 2. **Gate:** A.
- **Files:** `docs/spikes/phase-1-obsidian-templates.md`; the vault itself (outside the repo).
- **Depends on:** P1-04.
- **Agent:** user, orchestrator verifies (orchestrator runs the script; user does the Obsidian checks). **Reviewers:** `code-reviewer` on the results record.
- **Procedure:** run `init_vault.py` on `/mnt/d/sbw-scratch/Template Check`;
  user opens it in Obsidian, applies section 3.3, inserts each template into a
  new note, and opens today's note through the Daily notes plugin. Check:
  `{{title}}` becomes the note name; `id` is 14 digits; `created` is today; the
  Properties panel shows every key; Daily notes creates
  `01-Daily/YYYY/YYYY-MM-DD.md` with `# Standup - YYYY-MM-DD`; save a copy of
  that untouched daily note and of a note after a Properties-panel edit, which
  replace the synthetic fixture files from P1-06 (then re-run the tests listed
  there); record
  whether editing a property in the Properties UI reformats the YAML (and the
  diff); renaming a project note updates a `project: "[[...]]"` value in
  another note. If any check fails, return to P1-03. Then run `init_vault.py`
  on `/mnt/d/Second Brain`, open it in Obsidian, apply section 3.3 again with
  **Sync off** (C14), and commit `.obsidian/` settings with WSL git.
- **Run:** `git -C "/mnt/d/Second Brain" log --oneline && git -C "/mnt/d/Second Brain" config --local --list && git -C "/mnt/d/Second Brain" remote -v`.
- **Acceptance:** results document records each check and "Sync off"; the
  real vault exists with one or two commits, no remote and the section 2.6
  config; scratch vault deleted.

### Step 3: Skill, commands, fixture, parser, checker

#### P1-06 Golden sample vault

- **Goal:** the shared fixture that the parser, checker, commands, indexer,
  writer and API are all tested against.
- **Step:** 3. **Gate:** A.
- **Files:** `fixtures/golden-vault/{README.md,vault/,expected/index.json,expected/carry-forward/new-note/,expected/carry-forward/untouched-note/,expected/carry-forward/touched-note/}`, `claude/tests/test_fixture.py`.
- **Depends on:** P1-03.
- **Agent:** `qa-test-engineer`. **Reviewers:** `code-reviewer`.
- **Fixture must contain** (about 40 notes): each of the six types valid; a
  note without frontmatter; malformed YAML; unterminated frontmatter; duplicate
  keys; duplicate `id`; missing `id`; unknown keys and comments; a note in
  Obsidian's own property formatting (synthetic, see below); CRLF file; BOM file; empty file; non-ASCII and space names;
  every link form of section 2.8, including two notes with the same name in
  different folders, a bare link to that name (ambiguous), a folder-qualified
  link to one of them, unresolved links, links in frontmatter lists, and fake
  links and tags inside code; inline and frontmatter tags; tasks in every
  status with past, today and future `due`; `project` values as a wikilink, a
  folder-qualified wikilink and a plain slug; two project notes and one
  unknown project slug; two daily notes with a gap day; captures in each
  status; a copy of the templates in `08-System/Templates/`; `.obsidian/`,
  `.trash/`, a writer temp file and a `.sbignore`-listed file (all ignored).
  `expected/index.json` gives, per indexed path: type, title, status, priority,
  project slug, due, created, note_id, tags, link targets, parse_error
  presence. Three carry-forward scenarios (section 2.2): `new-note` (no note
  for the scenario date), `untouched-note` (an untouched note as Obsidian
  creates it) and `touched-note` (a note the user has typed in; expected
  unchanged), each with input date and expected output. The reference date for
  every date-relative expectation is `2026-10-09` (section 2.12).
- **Section 2.10 to 2.12 cases:** inline tags next to `[[A#Heading]]`,
  `[[#H]]` and `![[A#^b]]` (none are tags); `#1984` (not a tag), `#y1984`,
  `#eng/backend`, `#eng/`, `#Eng` and `#eng` in one note, `a#b`; frontmatter
  `tags` as a comma string with spaces, with a `#`-prefixed item, a numeric
  item and an item with internal whitespace; an unknown `type` (`Meeting`) and
  a non-string `type`; a note linking the same target several times with
  different spellings and an embed; a note without a trailing newline and one
  with several trailing blank lines (for the writer's end-of-file rule);
  invalid `due` values (`next week`, `2026-13-01`) on a `planned` task and a
  YAML timestamp `due`; in the previous daily note: an unchecked Follow-up
  linking a task, an unchecked Today item linking a task, an unresolved link in
  a Today item, duplicate free-text items within one section and the same text
  in both Today and Follow-ups, `- [x]`, `- [X]` and `- [/]` items, and
  `*`-bulleted and indented checkboxes; two blocked tasks with different due
  dates. `README.md` lists, per note, the checker codes (section 2.11) it must
  produce, so the checker's expected failures and warnings are fixed.
- **Obsidian-created samples:** this task writes **synthetic** versions of the
  two Obsidian-shaped files (the property-formatted note and the untouched
  daily note), marked as such in `README.md`. There is no hard dependency on
  P1-05: when P1-05 produces the real files, the orchestrator replaces the
  synthetic ones and re-runs the affected tests (P1-07 parser tests, the
  `/daily` and `/standup` scenarios of P1-13, and, once it exists, the
  untouched-note tests of P1-23).
- **Tests first:** `test_fixture.py` asserts the fixture's templates are
  byte-identical to the seeds and that every bullet above is present (by a
  manifest in `README.md`).
- **Run:** `uv run --project claude pytest claude/tests/test_fixture.py`.
- **Acceptance:** tests pass; `README.md` maps every fixture note to the rule it
  exercises.

#### P1-07 Markdown and frontmatter parser (Gate A)

- **Goal:** a pure-Python parser, with no Django imports, that turns file bytes
  into the fields of `Note`, its links and tags; built and tested in WSL with
  `uv` before the spike (C15).
- **Step:** 5 (allowed ahead of the spike). **Gate:** A.
- **Files:** `backend/pyproject.toml` and `backend/uv.lock` (minimal: ruamel.yaml, pytest, ruff; P1-17 extends them), `backend/vault/{__init__.py,parser.py,links.py,slug.py,conventions.py}`, `backend/tests/{test_parser.py,test_links.py,test_slug.py}`.
- **Depends on:** P1-06.
- **Agent:** `backend-engineer-python`. **Reviewers:** `code-reviewer`.
- **Tests first:** parametrised over `fixtures/golden-vault/expected/index.json`:
  every fixture note parses to its expected fields; malformed cases set
  `parse_error` and never raise; BOM and CRLF handled; links and the
  one-row-per-target link set per section 2.8; types, tags and dates per
  section 2.10; project values per section 2.1 (wikilink,
  folder-qualified, alias, plain slug); `conventions.py` holds types, folders,
  status vocabularies and the sanitising character sets; importing
  `vault.parser` does not import Django.
- **Run:** `cd backend && uv run pytest tests/test_parser.py tests/test_links.py tests/test_slug.py && uv run ruff check vault tests`.
- **Acceptance:** tests and ruff pass in WSL without Docker.

#### P1-08 Vault conformance checker

- **Goal:** a CLI that validates any vault directory against the conventions by
  importing the parser and `conventions.py`, not by re-implementing them.
- **Step:** 3. **Gate:** A.
- **Files:** `backend/vault/conformance.py`, `backend/tests/test_conformance.py`.
- **Depends on:** P1-07, P1-04.
- **Agent:** `qa-test-engineer`. **Reviewers:** `code-reviewer`.
- **Checks:** exactly the failures F1 to F8 and warnings W1 to W6 of section
  2.11, with required keys per type as listed there. A `project` or
  `triaged_to` link whose stem is not unique on disk is warning W3
  ("ambiguous"), not a failure, because the stem may have become duplicated
  after the link was written; the folder-qualified rule is enforced only by the
  writer and command tests on freshly written notes. Output: one line per
  problem with its code and path. Exit code 0 when there are no failures
  (warnings are printed), 1 otherwise.
- **Tests first:** the checker passes on a fresh `init_vault.py` vault; on the
  golden vault it reports exactly the codes per note listed in the fixture's
  `README.md`; a bare `project` link to a duplicated stem yields W3 and exit
  code 0; a static
  test asserts `conformance.py` defines no YAML parsing or link regex of its own
  (imports only).
- **Run:** `cd backend && uv run pytest tests/test_conformance.py && uv run python -m vault.conformance ../fixtures/golden-vault/vault`.
- **Acceptance:** tests pass; the CLI output on the golden vault matches the
  README's expected codes exactly.

#### P1-09 Install script

- **Goal:** install and uninstall the skill and commands into a Claude Code
  config directory without overwriting files it did not install.
- **Step:** 3. **Gate:** A.
- **Files:** `claude/install.sh`, `claude/tests/test_install.py`.
- **Depends on:** none (layout fixed in section 6; tests use dummy files).
- **Agent:** `devops-cloud-engineer`. **Reviewers:** `code-reviewer`, `security-engineer` (writes into `~/.claude`).
- **Tests first:** with `--target <tmp>`: installs `skills/second-brain/` and
  `commands/*.md` by copy; writes a manifest; re-running updates in place;
  refuses (non-zero, no partial install) when a target file exists that is not
  in the manifest; `--uninstall` removes exactly the manifest's files; never
  touches `CLAUDE.md`, `settings.json` or `docs/`; `--dry-run` writes nothing.
- **Run:** `uv run --project claude pytest claude/tests/test_install.py`.
- **Acceptance:** tests pass; `shellcheck` clean if available, otherwise noted.

#### P1-10 Command scenario tests (written first)

- **Goal:** a headless test harness and failing scenarios for every command, so
  the command tasks are test-driven (C16).
- **Step:** 3. **Gate:** A.
- **Files:** `claude/tests/commands/{conftest.py,test_*.py}`.
- **Depends on:** P1-06, P1-08, P1-09.
- **Agent:** `qa-test-engineer`. **Reviewers:** `code-reviewer`.
- **Harness:** for each test, copy `fixtures/golden-vault/vault` to a temp dir
  and `git init` it; install the skill and commands with
  `install.sh --target <tmpcwd>/.claude` (project scope, so `~/.claude` is not
  touched); run `claude -p "<command> <args>" --output-format json` from
  `<tmpcwd>` with `SECOND_BRAIN_VAULT=<tmp vault>`,
  `SECOND_BRAIN_TEST_MODE=1`, `SECOND_BRAIN_TODAY=2026-10-09` (section 2.12),
  `--add-dir <tmp vault>` and the fixed tool allowlist; then assert on the file
  system and run
  `python -m vault.conformance` on the result. Marked
  `@pytest.mark.commands`, excluded from the default run, run at task
  acceptance and at the final phase check.
- **Two-turn pattern** (review S-1) for commands that need confirmation
  (`/triage` batch approval, `/task ... status:done` with evidence, `/eod`
  status changes): turn 1 runs the command and the test asserts the vault is
  unchanged except for permitted automatic writes (high-confidence
  `classification`); turn 2 calls `claude -p --resume <session_id>` with "yes"
  or "no" (the session id comes from turn 1's JSON output), passing the tool
  allowlist again because the permission mode resets on resume, and asserts the
  outcome for each answer.
- **Assertions:** files created in the right folder with the right name;
  frontmatter keys and values, including `project` written as a wikilink and
  folder-qualified links where stems are duplicated; section headings intact;
  no other file changed (snapshot diff); conformance reports no failures.
  `/daily`: both carry-forward scenarios match the expected notes (the ordered
  item list of each section, compared after trimming whitespace), and a touched
  note is left unchanged. A guard scenario: with test mode set and
  `SECOND_BRAIN_VAULT` unset, the command refuses and writes nothing. `/eod`: one commit
  `eod: <date>`, second run amends, no remote; a planted secret stops the
  commit. A template edited in the temp vault changes the created note's shape
  (commands read the vault's templates).
- **Amendments after review (2026-10-05):** the harness reads
  `--output-format stream-json`, whose first event is the only reliable
  "command not found" signal. Daily notes are compared byte for byte, as the
  fixture's `scenario.json` files say. The checker assertion is "no new
  findings", warnings included. A session gets **no `git` permission**: the
  only git surface is `python3 -I <skill>/scripts/vault_git.py <verb>` (section
  4.2), allowed by exact rules, and every scenario except `/eod` asserts that
  `HEAD` and the index are unchanged. The session's environment is built from
  an allowlist, `printenv` is allowed only in the exact forms the skill uses,
  and the harness verifies the test vault's `.git/config` and hooks are
  unchanged before it runs git itself. The missing-folder error case cannot be
  reached through a command's arguments and is covered by the writer tests
  (P1-22). The live scenarios are not run until the harness has passed a
  security re-review.
- **Run:** `uv run --project claude pytest -m commands claude/tests/commands`.
- **Acceptance:** harness runs; every scenario fails for the expected reason
  (command not found).

#### P1-11 Create commands: `/capture`, `/task`, `/project`, `/decision`, `/knowledge`

- **Goal:** the five commands that create a note from a template, plus `/task`
  status changes.
- **Step:** 3. **Gate:** A.
- **Files:** `claude/commands/{capture,task,project,decision,knowledge}.md`.
- **Depends on:** P1-03, P1-10.
- **Agent:** `technical-writer`. **Reviewers:** `code-reviewer`.
- **Tests first:** the P1-10 scenarios for these five, including the two-turn
  `done` with evidence, a refused `/project` slug clash, and an unknown project
  on `/task`.
- **Run:** `uv run --project claude pytest -m commands claude/tests/commands -k "capture or task or project or decision or knowledge"`.
- **Acceptance:** scenarios pass on two consecutive runs.

#### P1-12 `/triage`

- **Goal:** classify inbox captures and, after one batch confirmation, convert
  or dismiss them.
- **Step:** 3. **Gate:** A.
- **Files:** `claude/commands/triage.md`.
- **Depends on:** P1-11.
- **Agent:** `technical-writer`. **Reviewers:** `code-reviewer`.
- **Tests first:** two-turn scenario with three fixture captures, per section
  2.13: high-confidence classification written in turn 1, nothing else; a
  low-confidence capture gets no `classification` written and appears as a
  suggestion; a capture whose kind has no Phase 1 target (for example a
  question) keeps `status: inbox`, gets its `classification` and no target
  note; "no" in turn 2 creates nothing; "yes" creates targets first, then sets
  `triaged` and `triaged_to`; capture files never moved or deleted.
- **Run:** `uv run --project claude pytest -m commands claude/tests/commands -k triage`.
- **Acceptance:** scenarios pass on two consecutive runs.

#### P1-13 `/daily` and `/standup`

- **Goal:** create or fill today's daily note with carry-forward, and produce
  the standup text.
- **Step:** 3. **Gate:** A.
- **Files:** `claude/commands/{daily,standup}.md`.
- **Depends on:** P1-03, P1-10.
- **Agent:** `technical-writer`. **Reviewers:** `code-reviewer`.
- **Tests first:** both golden carry-forward scenarios at the pinned date
  `2026-10-09`, which exercise every section 2.2 rule (Follow-up linking a task
  kept, Today item linking a task dropped, ordering, within-section
  de-duplication, invalid `due` not carried, checkbox markers); running
  `/daily` twice leaves the note unchanged; a touched note is never modified;
  `/standup` with input fills the right sections and prints all six headings.
- **Run:** `uv run --project claude pytest -m commands claude/tests/commands -k "daily or standup"`.
- **Acceptance:** scenarios pass on two consecutive runs.

#### P1-14 `/eod`

- **Goal:** close the day: append Done items, offer status changes, commit the
  vault once per day.
- **Step:** 3. **Gate:** A.
- **Files:** `claude/commands/eod.md`.
- **Depends on:** P1-13.
- **Agent:** `technical-writer`. **Reviewers:** `code-reviewer`, `security-engineer` (git in the vault, secret scan).
- **Tests first:** one commit per day with amend on rerun; refuses with a
  remote configured; planted secret stops the commit and names the file;
  two-turn scenario: no status change without "yes".
- **Run:** `uv run --project claude pytest -m commands claude/tests/commands -k eod`.
- **Acceptance:** scenarios pass on two consecutive runs.

#### P1-15 Install and smoke-test against the real vault

- **Goal:** install the commands into `~/.claude` and confirm daily use works
  before any app code exists.
- **Step:** 3 (gate for steps 2 and 3). **Gate:** A.
- **Files:** none in the repo; `~/.claude/skills/second-brain/`, `~/.claude/commands/`.
- **Depends on:** P1-05, P1-11, P1-12, P1-13, P1-14.
- **Agent:** user, orchestrator verifies (installing into `~/.claude` needs the user's go-ahead). **Reviewers:** `code-reviewer` on the install log.
- **Run:** `claude/install.sh --dry-run`, then `claude/install.sh`; in a new
  session run `/capture`, `/daily`, `/task`; then
  `cd backend && uv run python -m vault.conformance "/mnt/d/Second Brain"`.
- **Acceptance:** the `/` menu shows all nine commands and each runs this
  project's file; the checker passes on the real vault;
  `git -C "/mnt/d/Second Brain" status` shows only the expected new notes.

### Step 4: Repository scaffold

Each image is built and proven by the task that creates its manifest (review
M-2): the Compose task owns the shared file and `db`; the backend and frontend
skeleton tasks add their own Dockerfile and services.

#### P1-16 Compose base, database, environment

- **Goal:** `docker-compose.yml` with the `db` service, `.env.example`, ignore
  files and a static Compose check.
- **Step:** 4. **Gate:** B.
- **Files:** `docker-compose.yml` (`db` and volumes), `.env.example`, `.gitignore`, `scripts/check_compose.sh`.
- **Depends on:** P1-02.
- **Agent:** `devops-cloud-engineer`. **Reviewers:** `code-reviewer`, `security-engineer` (ports, secrets).
- **`.env.example` keys:** `VAULT_PATH`, `TZ=Asia/Manila`, `DJANGO_SECRET_KEY`
  (placeholder `change-me-not-a-secret`), `DJANGO_DEBUG=false`,
  `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `POSTGRES_DB`,
  `POSTGRES_USER`, `POSTGRES_PASSWORD`, `INDEXER_POLL_SECONDS=10`,
  `BACKEND_PORT=8000`, `FRONTEND_PORT=5173`. No app user credentials (C18).
- **Tests first:** `check_compose.sh`: `docker compose config` parses; every
  published port binds `127.0.0.1`; any `indexer` vault mount is `:ro`; no
  `test` service mounts the vault; `db` publishes no port; `.env` is
  gitignored; `.env.example` has every variable referenced in
  `docker-compose.yml`; neither `.env.example` nor `.env` (when present) sets
  `SECOND_BRAIN_TEST_MODE` or `SECOND_BRAIN_TODAY` (section 2.12). The script
  checks whichever services exist, so later tasks re-run it.
- **Run:** `scripts/check_compose.sh && docker compose up -d db && docker compose ps`.
- **Acceptance:** check passes; `db` healthy; `git grep` finds no real secret.

#### P1-17 Django skeleton, backend image, `backend`/`indexer`/`test` services

- **Goal:** Django project with settings from the environment, apps `vault` and
  `api`, health endpoint, the backend Dockerfile and its three services.
- **Step:** 4. **Gate:** B.
- **Files:** `backend/{Dockerfile,.dockerignore,pyproject.toml,uv.lock,manage.py,config/,api/,vault/clock.py,tests/conftest.py,tests/test_settings.py,tests/test_clock.py,tests/test_health.py,tests/test_isolation.py}`, `docker-compose.yml` (adds `backend`, `indexer`, `test`; the `test` service sets the section 2.12 variables).
- **Depends on:** P1-16, P1-07.
- **Agent:** `backend-engineer-python`. **Reviewers:** `code-reviewer`, `security-engineer` (settings, secrets, mounts).
- **Tests first:** settings refuse to load when `DJANGO_SECRET_KEY` is missing
  or equals the `.env.example` placeholder; `DEBUG` false by default;
  `TIME_ZONE` from `TZ`; `vault.clock.today()` returns the pinned date only
  when both section 2.12 variables are set, ignores either alone (with a
  warning), and otherwise returns the current date in `TIME_ZONE`;
  `GET /api/health/` returns 200 with
  `{"status": "ok"}` and 503 when the database is down; DRF default renderer
  JSON only, default permission `IsAuthenticated`; Django admin not installed;
  test isolation per section 6 (autouse fixture fails if `/vault` exists or is
  touched; vault root is a per-test temp dir); the P1-07 parser tests still
  pass inside the image.
- **Run:** `docker compose build backend && docker compose --profile test run --rm test pytest && docker compose --profile test run --rm test ruff check . && scripts/check_compose.sh`
- **Acceptance:** image builds; tests, ruff and Compose check pass;
  `docker compose up backend` serves `http://127.0.0.1:8000/api/health/`.

#### P1-18 Frontend skeleton, frontend image, `frontend` service

- **Goal:** Vite + React + TypeScript + Tailwind + shadcn/ui with ESLint,
  Vitest, the `/api` proxy and polling watch, plus its Dockerfile and service.
- **Step:** 4. **Gate:** B.
- **Files:** `frontend/{Dockerfile,.dockerignore,package.json,package-lock.json,vite.config.ts,vitest.config.ts,eslint.config.js,tsconfig*.json,components.json,index.html,src/}`, `docker-compose.yml` (adds `frontend`).
- **Depends on:** P1-16.
- **Agent:** `frontend-engineer`. **Reviewers:** `code-reviewer`.
- **Tests first:** a Vitest smoke test rendering the root component; a config
  test asserting the proxy target is `http://backend:8000` with `changeOrigin`
  false, `server.host` listens on all interfaces inside the container,
  `server.watch.usePolling` is true, and the allowed hosts accept `localhost`.
- **Run:** `docker compose build frontend && docker compose run --rm frontend npm run lint && docker compose run --rm frontend npm run test -- --run && docker compose run --rm frontend npx tsc --noEmit && scripts/check_compose.sh`
- **Acceptance:** image builds; all pass; `http://localhost:5173` renders; an
  edit to `src/` from Windows hot-reloads within 5 s; idle CPU of the
  `frontend` container recorded (D11).

#### P1-19 E2E stack script

- **Goal:** start, seed and stop the separate `sbw-e2e` Compose project with
  its own vault copy, database and user (section 6).
- **Step:** 4. **Gate:** B.
- **Files:** `scripts/e2e.sh`, `.env.e2e.example`, `scripts/tests/test_e2e_guard.sh`.
- **Depends on:** P1-17, P1-18.
- **Agent:** `devops-cloud-engineer`. **Reviewers:** `code-reviewer`, `security-engineer` (credential handling, vault guard).
- **Tests first:** guard test: the script exits non-zero when the project name
  is not `sbw-e2e` or `VAULT_PATH` resolves to `/mnt/d/Second Brain`; `up`
  copies the golden vault fresh; `.env.e2e.example` sets the section 2.12
  variables (`SECOND_BRAIN_TODAY=2026-10-09`) for the golden-vault mode and
  `up --vault-copy-of` unsets them so the real-vault copy is checked at the
  real date; `up --vault-copy-of <dir>` (exercised with a
  stand-in source directory, including one whose path is passed as the real
  vault path through a test override) copies the source, and the generated
  Compose configuration (`docker compose -p sbw-e2e config`) mounts only the
  copy, never the source path; a source path that does not exist is refused;
  `user` runs `createsuperuser --noinput` with
  `DJANGO_SUPERUSER_PASSWORD` only on that command line and only in the e2e
  project; `down -v` removes only `sbw-e2e` volumes.
- **Run:** `scripts/tests/test_e2e_guard.sh && scripts/e2e.sh up && scripts/e2e.sh user && curl -fsS http://127.0.0.1:8001/api/health/ && scripts/e2e.sh down`
- **Acceptance:** all pass; `docker volume ls` after `down` shows the real
  stack's volumes untouched.

### Step 5: Index models

The parser part of step 5 is P1-07 (Gate A).

#### P1-20 Index models and migrations

- **Goal:** `Note`, `Link`, `Tag` per design section F, with the stored
  `simple` search vector and trigram index.
- **Step:** 5. **Gate:** B.
- **Files:** `backend/vault/models.py`, `backend/vault/migrations/`, `backend/tests/test_models.py`.
- **Depends on:** P1-17.
- **Agent:** `backend-engineer-python`. **Reviewers:** `code-reviewer`.
- **Tests first (review S-9):** the **first** test applies the migrations to an
  empty test database; it is expected to expose whether PostgreSQL accepts the
  generated column as immutable. Documented fallback expression for the stored
  generated column:
  `to_tsvector('simple'::regconfig, coalesce(title,'') || ' ' || left(coalesce(body,''), 100000) || ' ' || path)`,
  with the body capped at 100,000 characters. Then: `path` unique; `note_id`
  indexed, not unique; `pg_trgm` enabled; a query for a ticket key like
  `LOADUP-123` and for a path fragment finds the note; deleting a `Note`
  cascades its `Link` rows and tag joins.
- **Run:** `docker compose --profile test run --rm test pytest tests/test_models.py && docker compose --profile test run --rm test python manage.py makemigrations --check --dry-run`
- **Acceptance:** tests pass; no pending migrations.

### Step 6: Indexer

#### P1-21 Indexer: sync, `reindex`, watch loop, `indexer` service

- **Goal:** incremental sync (add, edit, rename, delete), full rebuild, the
  rebuild-invariant test and the poll loop (merged per review O-1).
- **Step:** 6. **Gate:** B.
- **Files:** `backend/vault/indexer.py`, `backend/vault/management/commands/{sync_vault.py,reindex.py}`, `backend/tests/{test_indexer.py,test_rebuild_invariant.py,test_watch.py}`, `docker-compose.yml` (indexer command).
- **Depends on:** P1-07, P1-20, P1-19.
- **Agent:** `backend-engineer-python`. **Reviewers:** `code-reviewer`.
- **Tests first:** on a temp copy of the golden vault: first sync indexes
  exactly the non-ignored notes; edit, add, delete and rename (with and without
  `id`) produce the expected rows after one pass, a rename with matching `id`
  is logged as "moved"; an unchanged pass reads no file contents (counting
  opener); racy-file rule; ignore rules including `.sbignore`; duplicate and
  missing ids reported; `index_single_file(path)` updates one note; advisory
  lock prevents concurrent passes; `reindex` truncates only `Note`, `Link`,
  `Tag` and the join table without `CASCADE` (a created user and session
  survive it); rebuild invariant: after a sequence of incremental changes, a
  dump of all index rows (excluding primary keys) equals the dump after
  `reindex`; the watch loop runs N passes with an injected clock, survives a
  pass error, warns on over-budget passes and stops on SIGTERM.
- **Run:** `docker compose --profile test run --rm test pytest tests/test_indexer.py tests/test_rebuild_invariant.py tests/test_watch.py`
- **Acceptance:** tests pass; `sync_vault` prints the one-line JSON summary;
  in the `sbw-e2e` project (`scripts/e2e.sh up`, then
  `docker compose -p sbw-e2e --env-file .env.e2e up -d indexer`), an edit made
  in Obsidian to the e2e vault copy is indexed within two poll intervals,
  checked with `docker compose -p sbw-e2e --env-file .env.e2e exec backend python manage.py sync_vault`
  output; the real project's database is never used. Then `scripts/e2e.sh down`.

### Step 7: Vault writer

#### P1-22 Writer: confinement, sanitising, atomic create from template

- **Goal:** the only app code path that writes vault files, for creating notes.
- **Step:** 7. **Gate:** B.
- **Files:** `backend/vault/{writer.py,sanitize.py,templating.py}`, `backend/tests/{test_writer_create.py,test_sanitize.py,test_templating.py}`.
- **Depends on:** P1-17, P1-07.
- **Agent:** `backend-engineer-python`. **Reviewers:** `code-reviewer`, `security-engineer`.
- **Tests first:** placeholder subset of section 3.1 (and rejection of other
  tokens); every sanitising rule of section 2.5, using the constants in
  `conventions.py`; type-to-folder mapping; daily year folder created on
  demand; rejects `..`, absolute paths, symlinked components, ignored folders,
  non-`.md`; same-folder case-insensitive collision returns a conflict while a
  same name in another folder is allowed; uniqueness and emitted-link checks
  read the filesystem (a stale index cannot change the result); `project` is
  written as a wikilink, folder-qualified when the stem is duplicated on disk;
  several notes in one operation get ids one second apart; temp file pattern;
  temp file removed on failure; a crash between temp write and rename leaves
  the target untouched; created files are LF, UTF-8, owner as the spike
  recorded; templates read from `<vault>/08-System/Templates/`.
- **Run:** `docker compose --profile test run --rm test pytest tests/test_writer_create.py tests/test_sanitize.py tests/test_templating.py`
- **Acceptance:** tests pass; `python -m vault.conformance` passes on a vault
  copy after creates.

#### P1-23 Writer: frontmatter edit, append, fill untouched daily note

- **Goal:** round-trip frontmatter edits, section appends and the untouched
  daily-note fill, all with the on-disk hash check.
- **Step:** 7. **Gate:** B.
- **Files:** `backend/vault/writer.py`, `backend/tests/test_writer_edit.py`.
- **Depends on:** P1-22.
- **Agent:** `backend-engineer-python`. **Reviewers:** `code-reviewer`, `security-engineer`.
- **Tests first:** setting `status` preserves unknown keys, key order,
  comments, quoting and the body byte for byte, including the Obsidian-formatted
  fixture note; CRLF and BOM preserved; `expected_hash` mismatch against the
  file re-read immediately before the rename raises a conflict and leaves the
  file unchanged (simulate an Obsidian edit in between); malformed frontmatter
  refused; append-to-section follows every rule of section 2.4, including the
  end-of-file rule 8 on the fixture notes without a trailing newline and with
  several trailing blank lines; the
  "untouched" predicate of section 2.2 is true for the fixture's untouched note
  and false after any one-character edit to a section; with an **edited daily
  template** in the temp vault (an extra section and a renamed heading), a note
  rendered from that template counts as untouched, a note rendered from the
  original template counts as touched, and the fill inserts carry-forward items
  correctly; `done` with evidence appends under `## Notes`.
- **Run:** `docker compose --profile test run --rm test pytest tests/test_writer_edit.py`
- **Acceptance:** tests pass.

### Step 8: API

#### P1-24 API contract (OpenAPI)

- **Goal:** the committed OpenAPI schema for every endpoint in section 5, with
  serializers and routing; unimplemented views return `501`.
- **Step:** 8. **Gate:** B.
- **Files:** `backend/api/{urls.py,serializers.py,views/}`, `backend/openapi.yaml`, `backend/tests/test_schema.py`.
- **Depends on:** P1-20.
- **Agent:** `backend-engineer-python`. **Reviewers:** `code-reviewer`, `security-engineer` (auth surface).
- **Tests first:** the committed `openapi.yaml` equals freshly generated
  output; every path and method of section 5 is present; every path except
  health, csrf and login declares session auth. Views are split into one module
  per area (`notes`, `captures`, `standups`, `projects`, `dashboard`, `search`,
  `index`, `auth`) so later tasks do not edit the same file.
- **Run:** `docker compose --profile test run --rm test python manage.py spectacular --file /tmp/openapi.yaml --validate --fail-on-warn && docker compose --profile test run --rm test pytest tests/test_schema.py`
- **Acceptance:** both pass with no warnings.

#### P1-25 Authentication

- **Goal:** single-user session login with CSRF enforced (C10); the user is
  created by hand (C18).
- **Step:** 8. **Gate:** B.
- **Files:** `backend/api/views/auth.py`, `backend/config/settings.py`, `backend/tests/test_auth.py`.
- **Depends on:** P1-24.
- **Agent:** `backend-engineer-python`. **Reviewers:** `code-reviewer`, `security-engineer`.
- **Tests first** (users created by pytest-django fixtures): login sets an
  HttpOnly, SameSite=Lax session cookie and rotates the session; unsafe
  requests without a valid CSRF token are rejected; wrong credentials return
  400 without saying which field; sixth login attempt in a minute is
  throttled; every session-auth endpoint returns 401/403 when anonymous
  (parametrised over the schema's paths); logout clears the session; no code
  path creates a user from environment variables.
- **Run:** `docker compose --profile test run --rm test pytest tests/test_auth.py`
- **Acceptance:** tests pass; backend entrypoint runs `migrate` and nothing
  that creates users.

#### P1-26 Read endpoints: notes, lookup, projects, dashboard

- **Goal:** the read side the pages use.
- **Step:** 8. **Gate:** B.
- **Files:** `backend/api/views/{notes.py,projects.py,dashboard.py}`, `backend/vault/queries.py`, `backend/tests/{test_api_notes.py,test_api_projects.py,test_api_dashboard.py}`.
- **Depends on:** P1-25, P1-21.
- **Agent:** `backend-engineer-python`. **Reviewers:** `code-reviewer`.
- **Tests first:** against the indexed golden vault: each filter and ordering,
  with `path` as final tiebreaker; lookup by path and by id (duplicate id gives
  409 with candidates); the `links` map gives path and state for resolved,
  ambiguous and unresolved targets; backlinks; project slug resolution per
  section 2.1; dashboard sections per design E with the index summary;
  invalid `due` values excluded from `overdue`, due-today and date filters and
  sorted with "no due" (section 2.10);
  `today` and `overdue` frozen at 15:59 and 16:01 UTC (either side of Manila
  midnight, review O-8); bounded query count (no N+1).
- **Run:** `docker compose --profile test run --rm test pytest tests/test_api_notes.py tests/test_api_projects.py tests/test_api_dashboard.py`
- **Acceptance:** tests pass; responses match `openapi.yaml`.

#### P1-27 Search, index status, index refresh

- **Goal:** full-text search and the endpoints behind the Index Status page.
- **Step:** 8. **Gate:** B.
- **Files:** `backend/api/views/{search.py,index.py}`, `backend/tests/{test_api_search.py,test_api_index.py}`.
- **Depends on:** P1-25, P1-21.
- **Agent:** `backend-engineer-python`. **Reviewers:** `code-reviewer`.
- **Tests first:** ticket keys, identifiers and path fragments found (no
  stemming); title typo found by trigram; every result has `source`; status
  reports each problem category present in the fixture (parse errors, missing
  ids, duplicate ids, ambiguous links, unknown and duplicate project slugs,
  unknown statuses, invalid dates); `test_mode` and the pinned date appear only
  when both section 2.12 variables are set; refresh picks up a file changed on
  disk and returns the pass summary.
- **Run:** `docker compose --profile test run --rm test pytest tests/test_api_search.py tests/test_api_index.py`
- **Acceptance:** tests pass.

#### P1-28 Write endpoints: create, capture, status, triage

- **Goal:** the API write actions (C17), each through the writer, then
  re-indexing the one file.
- **Step:** 8. **Gate:** B.
- **Files:** `backend/api/views/{notes.py,captures.py}`, `backend/api/serializers.py`, `backend/tests/test_api_writes.py`.
- **Depends on:** P1-25, P1-23, P1-21.
- **Agent:** `backend-engineer-python`. **Reviewers:** `code-reviewer`, `security-engineer`.
- **Tests first:** create per type returns the indexed note and the file
  exists; same-folder collision 409; same name in another folder allowed;
  unknown project 422; status change validates the per-type vocabulary;
  `evidence` appended under `## Notes` on `done`; stale `expected_hash` 409 with
  the file unchanged; malformed frontmatter 422; triage writes the target
  first, then the capture; **partial failure** (review S-5): when the capture
  edit fails (simulated 409), the response carries `created_target`, the
  target exists, the capture is unchanged, and a retry with `existing_target`
  completes without creating a second note; `existing_target` goes through the
  writer's path confinement before any existence check, so `..`, an absolute
  path, a symlinked component, an ignored folder or a non-`.md` value is
  rejected with 400 and no file is read or written; triage never deletes or moves the
  capture; a failed file write indexes nothing; the request body cannot carry a
  path for create.
- **Run:** `docker compose --profile test run --rm test pytest tests/test_api_writes.py`
- **Acceptance:** tests pass; `python -m vault.conformance` passes on the vault
  copy after the run.

#### P1-29 Standups today with carry-forward

- **Goal:** create or fill today's daily note with section 2.2 carry-forward,
  read it, and append to it.
- **Step:** 8. **Gate:** B.
- **Files:** `backend/vault/carry_forward.py`, `backend/api/views/standups.py`, `backend/tests/{test_carry_forward.py,test_api_standups.py}`.
- **Depends on:** P1-28.
- **Agent:** `backend-engineer-python`. **Reviewers:** `code-reviewer`.
- **Tests first:** both golden scenarios produce exactly the expected note
  (`new-note` returns 201, `untouched-note` returns 200 with `filled: true`); a
  touched note returns 200 with `filled: false` and is unchanged; a second POST
  is a no-op; POST runs a sync pass first (a task set to `done` on disk just
  before the POST is not carried, review S-6); a concurrent Obsidian edit
  during fill yields 409 and no partial write; GET 404 preview equals what POST
  would write; append uses section 2.4 and the hash check; "today" is the
  Manila date at 15:59 and 16:01 UTC.
- **Run:** `docker compose --profile test run --rm test pytest tests/test_carry_forward.py tests/test_api_standups.py`
- **Acceptance:** tests pass.

#### P1-30 API-level rebuild invariant and permission matrix

- **Goal:** prove at the API level that dropping the index loses nothing, and
  that no endpoint is reachable without a session.
- **Step:** 8. **Gate:** B.
- **Files:** `backend/tests/{test_api_rebuild_invariant.py,test_api_permissions.py}`.
- **Depends on:** P1-26, P1-27, P1-29.
- **Agent:** `qa-test-engineer`. **Reviewers:** `code-reviewer`.
- **Tests first:** a scripted sequence of API writes and disk edits; capture
  every read endpoint's response (all pages, lookups by path and id, projects,
  dashboard, fixed search queries, index status); run `reindex`; capture again;
  compare excluding timing fields; the test user can still log in after
  `reindex`. Every path in `openapi.yaml` is exercised anonymous, with a
  session but no CSRF token, and with a valid session.
- **Run:** `docker compose --profile test run --rm test pytest tests/test_api_rebuild_invariant.py tests/test_api_permissions.py`
- **Acceptance:** tests pass; the full backend suite
  `docker compose --profile test run --rm test pytest` passes.

### Step 9: Frontend

Component and hook tests mock the API client module. Each page task also has a
manual check against the running stack, which is why it depends on its backend
endpoint task. Page order follows the master plan, with Index Status last.

#### P1-31 App shell, API client, authentication, CSRF through the proxy

- **Goal:** layout and navigation, the typed API client, login and CSRF
  handling, and an automated proof that CSRF works through the Vite proxy
  (review S-15).
- **Step:** 9. **Gate:** B.
- **Files:** `frontend/src/{main.tsx,routes.tsx,api/,components/AppShell.tsx,features/auth/}`, `scripts/check_csrf_proxy.sh`.
- **Depends on:** P1-18, P1-19, P1-24, P1-25.
- **Agent:** `frontend-engineer`. **Reviewers:** `code-reviewer`, `security-engineer` (auth, CSRF in the client).
- **Tests first:** types generated from `backend/openapi.yaml` compile; the
  client sends `X-CSRFToken` from the cookie on unsafe methods and never
  otherwise; 401/403 redirects to login and back; navigation shows exactly
  Dashboard, Tasks, Projects, Standups, Inbox, Knowledge, Decisions, Search,
  Index Status; null values render `N/A`. `check_csrf_proxy.sh` runs against
  the e2e stack's frontend port with curl: login with the CSRF token succeeds;
  login without it returns 403; login with the token but `Origin:
  http://evil.example` returns 403.
- **Run:** `docker compose run --rm frontend npm run test -- --run src/api src/features/auth src/components && docker compose run --rm frontend npm run lint && scripts/e2e.sh up && scripts/e2e.sh user && scripts/check_csrf_proxy.sh && scripts/e2e.sh down`
- **Acceptance:** all pass; the user logs in to the real stack (after
  `createsuperuser`) through `http://localhost:5173`.

#### P1-32 Note reader (shared detail view)

- **Goal:** one note detail view used by every page: metadata, rendered body,
  links, backlinks, parse errors.
- **Step:** 9. **Gate:** B.
- **Files:** `frontend/src/components/NoteReader.tsx`, `frontend/src/features/note/`.
- **Depends on:** P1-31, P1-26.
- **Agent:** `frontend-engineer`. **Reviewers:** `code-reviewer`, `security-engineer` (rendering vault content).
- **Tests first:** Markdown renders without raw HTML (`<script>` and an
  `onerror` attribute render as text); wikilinks become in-app links using the
  API's `links` map with no client-side normalisation, marked when ambiguous or
  unresolved; external links get `rel="noopener noreferrer"`; parse errors are
  shown.
- **Run:** `docker compose run --rm frontend npm run test -- --run src/components/NoteReader src/features/note`
- **Acceptance:** tests pass; golden-vault notes render in the running app.

#### P1-33 Dashboard page

- **Goal:** design E's dashboard, the five quick actions and the small index
  status summary linking to the Index Status page.
- **Step:** 9. **Gate:** B.
- **Files:** `frontend/src/features/dashboard/`, `frontend/src/components/QuickActions.tsx`.
- **Depends on:** P1-32, P1-28, P1-29.
- **Agent:** `frontend-engineer`. **Reviewers:** `code-reviewer`.
- **Tests first:** each section renders from a fixture response, empty states,
  `N/A`; each quick action calls the right endpoint and shows 409/422 errors;
  the index summary shows last pass time and problem count and links to
  `/index-status`.
- **Run:** `docker compose run --rm frontend npm run test -- --run src/features/dashboard src/components/QuickActions`
- **Acceptance:** tests pass; manual check against the running stack recorded.

#### P1-34 Tasks page

- **Goal:** task list and status board with filters, create and status change.
- **Step:** 9. **Gate:** B.
- **Files:** `frontend/src/features/tasks/`.
- **Depends on:** P1-32, P1-28.
- **Agent:** `frontend-engineer`. **Reviewers:** `code-reviewer`.
- **Tests first:** filters map to query parameters; board columns are the seven
  task statuses; moving to `done` asks for confirmation and optional evidence;
  a 409 shows "changed in Obsidian, reload" and refetches.
- **Run:** `docker compose run --rm frontend npm run test -- --run src/features/tasks`
- **Acceptance:** tests pass; manual check recorded.

#### P1-35 Inbox page

- **Goal:** captures awaiting triage, quick capture and triage actions.
- **Step:** 9. **Gate:** B.
- **Files:** `frontend/src/features/inbox/`.
- **Depends on:** P1-32, P1-28.
- **Agent:** `frontend-engineer`. **Reviewers:** `code-reviewer`.
- **Tests first:** lists only `status: inbox` captures; capture form posts and
  the item appears; triage dialog offers the nine classifications and six
  actions and sends `expected_hash`; a partial-failure response offers "retry"
  that sends `existing_target`.
- **Run:** `docker compose run --rm frontend npm run test -- --run src/features/inbox`
- **Acceptance:** tests pass; manual check recorded.

#### P1-36 Standups page

- **Goal:** daily notes by date; start or fill today's standup with
  carry-forward; append to a section.
- **Step:** 9. **Gate:** B.
- **Files:** `frontend/src/features/standups/`.
- **Depends on:** P1-32, P1-29.
- **Agent:** `frontend-engineer`. **Reviewers:** `code-reviewer`.
- **Tests first:** list newest first; "Start standup" shows the preview then
  creates; an untouched note offers "Fill with carry-forward"; a touched note
  is shown as-is; the append form targets one of the six sections.
- **Run:** `docker compose run --rm frontend npm run test -- --run src/features/standups`
- **Acceptance:** tests pass; manual check recorded.

#### P1-37 Projects, Knowledge, Decisions and Search pages

- **Goal:** the four browse-and-read pages (merged per review O-1).
- **Step:** 9. **Gate:** B.
- **Files:** `frontend/src/features/{projects,knowledge,search}/`.
- **Depends on:** P1-32, P1-27.
- **Agent:** `frontend-engineer`. **Reviewers:** `code-reviewer`.
- **Tests first:** Projects lists status and open-task count, detail sections
  render, unknown slug shows not found; Knowledge lists `type=lesson`,
  Decisions lists `type=decision` with status filter; Search is debounced and
  URL-synced, each result shows type, title, snippet and source; empty and
  error states for all four.
- **Run:** `docker compose run --rm frontend npm run test -- --run src/features/projects src/features/knowledge src/features/search`
- **Acceptance:** tests pass; manual check recorded.

#### P1-38 Index Status page

- **Goal:** the dedicated Index Status page (C24): last sync, counts, parse
  errors, missing ids, duplicate ids, ambiguous links, and the "Refresh index"
  action.
- **Step:** 9. **Gate:** B.
- **Files:** `frontend/src/features/index-status/`.
- **Depends on:** P1-32, P1-27.
- **Agent:** `frontend-engineer`. **Reviewers:** `code-reviewer`.
- **Tests first:** each category renders with its count and a list of affected
  notes linking to the note reader (unknown project slugs, unknown statuses and
  invalid dates included); empty categories show "None"; **Refresh**: clicking
  it calls `POST /api/index/refresh/` once, disables the button while running,
  shows the returned pass summary, refetches the status, and shows an error
  state on failure.
- **Run:** `docker compose run --rm frontend npm run test -- --run src/features/index-status`
- **Acceptance:** tests pass; manual check: a note broken on disk appears after
  Refresh.

### Step 10: End-to-end tests and README

#### P1-39 End-to-end tests

- **Goal:** Playwright tests for capture then triage to a task; create a task
  and move it to done; start a standup with carry-forward (including the
  untouched-note fill); search; plus an Index Status refresh.
- **Step:** 10. **Gate:** B.
- **Files:** `frontend/e2e/{playwright.config.ts,auth.setup.ts,*.spec.ts}`, `docker-compose.yml` (`e2e` profile).
- **Depends on:** P1-30, P1-33, P1-34, P1-35, P1-36, P1-37, P1-38.
- **Agent:** `qa-test-engineer`. **Reviewers:** `code-reviewer`.
- **Setup:** runs only in the `sbw-e2e` project (`scripts/e2e.sh up` and
  `user`); a setup project logs in once and saves `storageState`; the config
  refuses to start if `VAULT_PATH` is the real vault.
- **Tests first:** the five flows, each also asserting the resulting file on
  disk; one flow where the note is edited on disk between load and save and
  the UI shows the conflict.
- **Run:** `scripts/e2e.sh up && scripts/e2e.sh user && docker compose -p sbw-e2e --env-file .env.e2e --profile e2e run --rm e2e npx playwright test && scripts/e2e.sh down`
- **Acceptance:** all pass on two consecutive runs.

#### P1-40 README and run instructions

- **Goal:** a README that gets the user from clone to a running stack and
  explains recovery.
- **Step:** 10. **Gate:** B.
- **Files:** `README.md`, `scripts/check_readme.sh`.
- **Depends on:** P1-39, P1-15.
- **Agent:** `technical-writer`. **Reviewers:** `code-reviewer`.
- **Content:** prerequisites (Docker WSL integration); `.env` from
  `.env.example` and replacing the secret-key placeholder; `docker compose up`;
  **creating the user by hand** with
  `docker compose run --rm backend python manage.py createsuperuser`, and
  doing it again after any database rebuild (C18); installing the commands; the
  vault's Obsidian settings (Sync off); running each test suite (default,
  `-m commands`, e2e); `reindex` (index tables only; the user survives);
  rollback and recovery from the master plan; troubleshooting for the spike
  findings.
- **Tests first:** `check_readme.sh` extracts every fenced shell block marked
  `# verify` and runs it in a scratch checkout; only blocks that do not need
  Docker carry the marker (review O-2).
- **Run:** `scripts/check_readme.sh`
- **Acceptance:** script passes; linked table of contents; every
  `.env.example` key documented.

### Step 11: Real use and phase review

#### P1-41 One week of real use, then the phase review

- **Goal:** use the vault, commands and dashboard for daily work for one week,
  then review the phase.
- **Step:** 11. **Gate:** B.
- **Files:** `docs/plan/phase-1-review.md`.
- **Depends on:** P1-40.
- **Agent:** user, with `technical-writer` drafting the review from the user's
  notes and the Index Status page. **Reviewers:** `code-reviewer` on the
  document; the user approves the phase.
- **Run:** full suites: `docker compose --profile test run --rm test pytest`,
  `docker compose run --rm frontend npm run test -- --run`,
  `uv run --project claude pytest`, `uv run --project claude pytest -m commands claude/tests/commands`.
  Real-vault rebuild check without touching the real stack:
  `scripts/e2e.sh up --vault-copy-of "/mnt/d/Second Brain"` and
  `scripts/e2e.sh user`, capture the API read responses from the `sbw-e2e`
  project, run `reindex` there, capture again and compare with the P1-30
  comparator, then `scripts/e2e.sh down`.
- **Acceptance:** all suites pass; the rebuild comparison is identical; the
  review lists what was used, what was not, scan timings from the indexer
  logs, and follow-ups for Phase 2.

---

## 10. Dependencies and parallelism

### Dependency table

| Task | Title | Depends on | Agent | Gate |
|---|---|---|---|---|
| P1-01 | Enable Docker in WSL | none | user | n/a |
| P1-02 | Mount spike | P1-01 | devops-cloud-engineer | A→B |
| P1-03 | Templates, conventions, vault README, skill | none | technical-writer | A |
| P1-04 | Vault init script | P1-03 | backend-engineer-python | A |
| P1-05 | Verify templates in Obsidian, create real vault | P1-04 | user | A |
| P1-06 | Golden sample vault | P1-03 | qa-test-engineer | A |
| P1-07 | Parser | P1-06 | backend-engineer-python | A |
| P1-08 | Conformance checker | P1-07, P1-04 | qa-test-engineer | A |
| P1-09 | Install script | none | devops-cloud-engineer | A |
| P1-10 | Command scenario tests | P1-06, P1-08, P1-09 | qa-test-engineer | A |
| P1-11 | Create commands | P1-03, P1-10 | technical-writer | A |
| P1-12 | `/triage` | P1-11 | technical-writer | A |
| P1-13 | `/daily`, `/standup` | P1-03, P1-10 | technical-writer | A |
| P1-14 | `/eod` | P1-13 | technical-writer | A |
| P1-15 | Install and smoke-test on real vault | P1-05, P1-11, P1-12, P1-13, P1-14 | user | A |
| P1-16 | Compose base, database, environment | P1-02 | devops-cloud-engineer | B |
| P1-17 | Django skeleton, backend image and services | P1-16, P1-07 | backend-engineer-python | B |
| P1-18 | Frontend skeleton, image and service | P1-16 | frontend-engineer | B |
| P1-19 | E2E stack script | P1-17, P1-18 | devops-cloud-engineer | B |
| P1-20 | Index models and migrations | P1-17 | backend-engineer-python | B |
| P1-21 | Indexer: sync, reindex, watch | P1-07, P1-20, P1-19 | backend-engineer-python | B |
| P1-22 | Writer: create | P1-17, P1-07 | backend-engineer-python | B |
| P1-23 | Writer: edit, append, untouched fill | P1-22 | backend-engineer-python | B |
| P1-24 | API contract | P1-20 | backend-engineer-python | B |
| P1-25 | Authentication | P1-24 | backend-engineer-python | B |
| P1-26 | Read endpoints | P1-25, P1-21 | backend-engineer-python | B |
| P1-27 | Search and index endpoints | P1-25, P1-21 | backend-engineer-python | B |
| P1-28 | Write endpoints | P1-25, P1-23, P1-21 | backend-engineer-python | B |
| P1-29 | Standups with carry-forward | P1-28 | backend-engineer-python | B |
| P1-30 | API rebuild invariant and permissions | P1-26, P1-27, P1-29 | qa-test-engineer | B |
| P1-31 | App shell, API client, auth, CSRF check | P1-18, P1-19, P1-24, P1-25 | frontend-engineer | B |
| P1-32 | Note reader | P1-31, P1-26 | frontend-engineer | B |
| P1-33 | Dashboard page | P1-32, P1-28, P1-29 | frontend-engineer | B |
| P1-34 | Tasks page | P1-32, P1-28 | frontend-engineer | B |
| P1-35 | Inbox page | P1-32, P1-28 | frontend-engineer | B |
| P1-36 | Standups page | P1-32, P1-29 | frontend-engineer | B |
| P1-37 | Projects, Knowledge, Decisions, Search pages | P1-32, P1-27 | frontend-engineer | B |
| P1-38 | Index Status page | P1-32, P1-27 | frontend-engineer | B |
| P1-39 | End-to-end tests | P1-30, P1-33, P1-34, P1-35, P1-36, P1-37, P1-38 | qa-test-engineer | B |
| P1-40 | README | P1-39, P1-15 | technical-writer | B |
| P1-41 | Real use and phase review | P1-40 | user + technical-writer | B |

### Graph

```text
GATE A (no Docker)
P1-03 ─┬─> P1-04 ──> P1-05 ───────────────────────────────────┐
       │     └─────────────────> P1-08 (also P1-07)           │
       ├─> P1-06 ──> P1-07 ──> P1-08 ─┐                       │
       │                              v                       │
P1-09 ────────────────────────────> P1-10 ─┬─> P1-11 ─> P1-12 ┤
P1-03 ────────────────────────────────────>┤                  ├─> P1-15 ─────────────┐
                                           └─> P1-13 ─> P1-14 ┘                      │
                                                                                     │
P1-01 ──> P1-02 ══ GATE B ══> P1-16 ─┬─> P1-17 (also needs P1-07) ─┬─> P1-20 ─┬─> P1-21 (also P1-07, P1-19)
                                     │                             │          └─> P1-24 ─> P1-25
                                     │                             └─> P1-22 (also P1-07) ─> P1-23
                                     └─> P1-18
P1-17 + P1-18 ──> P1-19
P1-25 + P1-21 ──> P1-26, P1-27
P1-25 + P1-23 + P1-21 ──> P1-28 ──> P1-29
P1-26 + P1-27 + P1-29 ──> P1-30
P1-18 + P1-19 + P1-24 + P1-25 ──> P1-31 ──> P1-32 (also P1-26)
P1-32 ──> P1-33 (P1-28, P1-29), P1-34 (P1-28), P1-35 (P1-28), P1-36 (P1-29),
          P1-37 (P1-27), P1-38 (P1-27)
P1-30 + P1-33..P1-38 ──> P1-39 ──> P1-40 (also P1-15) ──> P1-41
```

"P1-33..P1-38" means each of P1-33, P1-34, P1-35, P1-36, P1-37 and P1-38.

### Parallel waves

Tasks in one wave do not depend on each other. Where noted, run them one after
another to avoid editing the same file.

| Wave | Tasks | Note |
|---|---|---|
| A1 | P1-01, P1-03, P1-09 | P1-01 is the user's action. |
| A2 | P1-04, P1-06; P1-02 once P1-01 is done | |
| A3 | P1-05, P1-07 | |
| A4 | P1-08 | |
| A5 | P1-10 | |
| A6 | P1-11, P1-13 | Separate command files. |
| A7 | P1-12, P1-14 | |
| A8 | P1-15 | |
| B1 | P1-16 | |
| B2 | P1-17, P1-18 | Both add services to `docker-compose.yml`: merge one after the other. |
| B3 | P1-19, P1-20, P1-22 | |
| B4 | P1-21, P1-23, P1-24 | |
| B5 | P1-25 | |
| B6 | P1-26, P1-27, P1-28, P1-31 | View modules are split per area in P1-24, so the three backend tasks touch different files except `serializers.py`; merge in order. |
| B7 | P1-29, P1-32 | |
| B8 | P1-30, P1-33 to P1-38 | Separate feature folders; master-plan order recommended for one frontend agent. |
| B9 | P1-39 | |
| B10 | P1-40 | |
| B11 | P1-41 | |

### Critical path

By dependencies (13 tasks):
**P1-01 → P1-02 → P1-16 → P1-17 → P1-20 → P1-24 → P1-25 → P1-28 → P1-29 →
P1-33 → P1-39 → P1-40 → P1-41.**

In practice one frontend agent doing P1-33 to P1-38 in sequence is the longest
stretch. The other critical item is the user enabling Docker (P1-01): nothing
in Gate B starts until then.

**Can start before Docker is available:** P1-03 to P1-15 (Gate A, including the
parser P1-07 and the checker P1-08). P1-01 is the user's action; P1-02 needs
Docker.

---

## 11. Risks specific to this breakdown

| Risk | Effect | Mitigation |
|---|---|---|
| Command tests are non-deterministic and cost tokens | Flaky acceptance for P1-11 to P1-14 | Structural assertions; "passes on two consecutive runs"; opt-in marker (C16); the same rules are covered deterministically by the parser, writer and carry-forward tests on the same fixture. |
| Commands are prompts, not code | `/daily` may apply carry-forward slightly differently from the API | One written algorithm (section 2.2) in the skill; both golden scenarios used by both; the conformance checker runs on every command result. |
| Parser built before the Django project exists | `backend/pyproject.toml` created twice | P1-07 creates a minimal manifest; P1-17 extends it and re-runs the parser tests inside the image. |
| Command names shadowed by a built-in or plugin command | A command silently runs something else | Install script refuses to overwrite; P1-15 checks each name in the `/` menu. |
| Spike soft passes change parameters late | Poll interval, uid or racy window differ from this plan | The results document is an input to P1-16, P1-17, P1-21 and P1-22 briefs; parameters live in `.env`. |
| Obsidian reformats YAML when properties are edited in its UI | Round-trip expectations wrong | P1-05 records the behaviour; the fixture holds an Obsidian-formatted note; P1-23 tests it. |
| Manual user creation is forgotten after a rebuild | Cannot log in | README step (P1-40) and master-plan recovery text. No "no user exists" hint on the login page, because it would need an unauthenticated endpoint that reveals account state. |
| Real stack and e2e project run at once | Port or volume clashes | Separate project name, volumes and ports (5174, 8001); `e2e.sh` guard. |
| Filesystem walk for emitted links on every write | Slow writes on a large vault | One walk per operation; spike M1 gives the cost; the walk is stat-free (names only). |

---

## 12. Decisions confirmed 2026-10-05

Recorded in the design as C14 to C24 and applied throughout this plan.

| # | Decision | Where it lands in this plan |
|---|---|---|
| C14 | Obsidian Sync is off for the new vault. | Sections 2.6, 3.3; P1-05. |
| C15 | Only the parser is built before the mount spike, in WSL with `uv`; the conformance checker imports it. The writer and everything else wait for the spike. | Gates; P1-07, P1-08; P1-17 extends the manifest. |
| C16 | Headless `claude -p` command tests, opt-in marker, run at task acceptance and the final phase check. | P1-10 to P1-14, P1-41. |
| C17 | Write endpoints: generic create from template, generic status change, capture triage. | Section 5; P1-28. |
| C18 | The single Django user is created by hand with `createsuperuser` and re-created after any database rebuild; a deliberate exception to "the database holds no state of its own" (user account and sessions). No credentials in `.env`. Settings refuse the placeholder secret key. `reindex` truncates only the index tables. Tests and the e2e stack create their own users. | Sections 2.9, 6; P1-16, P1-17, P1-19, P1-21, P1-25, P1-40. |
| C19 | `project` is written as `"[[Project title]]"` by the writer and commands; the indexer derives the slug and still accepts a plain slug. The template keeps `project:` empty. | Sections 2.1, 3.2; P1-07, P1-22. |
| C20 | Within one operation, generated ids advance one second per note. | Section 2.9; P1-22. |
| C21 | A rename is delete plus add, logged as "moved" when the id matches; the API also looks notes up by id. | Sections 2.9, 5; P1-21, P1-26. |
| C22 | Duplicate names in different folders are allowed; ambiguous links resolve deterministically and are flagged; system-written links to a non-unique stem are folder-qualified; uniqueness checks read the filesystem. The same-folder case collision rule stays. | Sections 2.5, 2.8; P1-22. |
| C23 | Mount rule reads "no other host data path"; repository source and read-only fixtures may be mounted. | Section 6. |
| C24 | A dedicated Index Status page in Phase 1 navigation; the Dashboard keeps a small summary linking to it. | Sections 5, 6; P1-27, P1-31, P1-33, P1-38. |

There are no open user questions left for this plan.

---

## 13. Verification record

Checked against documentation through context7 on 2026-10-05:

- Obsidian core Templates variables `{{title}}`, `{{date}}`, `{{time}}` and the
  `:FORMAT` Moment.js syntax.
- Django 6.1 exists; Django 5.2 supports Python 3.10 to 3.14;
  `createsuperuser --noinput` reads `DJANGO_SUPERUSER_PASSWORD` and
  `DJANGO_SUPERUSER_<FIELD>` (used only by the e2e script).
- DRF requirements and the 3.17.2 upload-size security fix.
- drf-spectacular requirements and `spectacular --validate --fail-on-warn`.
- pytest-django compatibility; pytest 9.0 exists.
- ruamel.yaml round-trip behaviour and duplicate-key error (docs for 0.18.6).
- PostgreSQL 18 stored generated `tsvector` columns and `pg_trgm`; generated
  columns default to virtual; postgres 18+ image data layout.
- Vite 8 Node requirement, `server.proxy`, `server.host`,
  `server.watch.usePolling` and the WSL2 note; Vitest 4; React 19.2;
  shadcn/ui Vite + Tailwind 4; Playwright 1.63 auth setup.
- Claude Code: custom commands merged into skills; skill frontmatter fields.

Reported checked by the architecture review, not re-checked here:
`claude -p --resume <session-id>` with JSON output supports the two-turn
pattern, and the permission mode resets on each resume.

Not verified (judgment; the implementing task confirms):

- Exact current versions of drf-spectacular, pytest-django, ruamel.yaml beyond
  0.18, ruff, TypeScript, ESLint, React Testing Library, jsdom,
  openapi-typescript.
- That Django 5.2 officially lists PostgreSQL 18.
- That PostgreSQL accepts the generated search column as immutable (P1-20's
  first test; fallback documented).
- The Playwright image tag format and `network_mode: "service:frontend"` on
  Docker Desktop.
- Precedence between a personal command and a built-in of the same name.
- Obsidian behaviour: a Daily notes format containing `/` creating year
  folders; YAML reformatting by the Properties UI; rename updating wikilinks in
  frontmatter values (P1-05 checks these).
- Compose `.env` handling of an unquoted value with a space (spike M8).
