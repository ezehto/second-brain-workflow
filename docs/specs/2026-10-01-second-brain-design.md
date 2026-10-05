# Second Brain: Design Specification

| | |
|---|---|
| Status | Approved 2026-10-05; amended 2026-10-05 with C14 to C26 |
| Date | 2026-10-01 |
| Source brief | "Obsidian-First Engineering Second Brain & Operating System" master prompt |
| Companion | [`../plan/master-plan.md`](../plan/master-plan.md) |

This document is the initial deliverable the brief asks for (its section 48,
items A to J). It records what was inspected, what was decided, and what is
still open. Implementation detail for each phase lives in that phase's own plan.

## Contents

- [0. Intent](#0-intent)
  - [Confirmed decisions (2026-10-01)](#confirmed-decisions-2026-10-01)
- [A. Environment Assessment](#a-environment-assessment)
- [B. Current-State Assessment](#b-current-state-assessment)
- [C. Proposed Architecture](#c-proposed-architecture)
  - [Components](#components)
  - [Data flows](#data-flows)
  - [Write safety](#write-safety)
  - [Runtime topology (Docker Compose)](#runtime-topology-docker-compose)
  - [Security boundaries](#security-boundaries)
- [D. Vault Design](#d-vault-design)
  - [Folder structure](#folder-structure)
  - [Frontmatter](#frontmatter)
  - [Note identity and naming](#note-identity-and-naming)
  - [Ignored paths](#ignored-paths)
  - [Templates (Phase 1)](#templates-phase-1)
  - [Linking strategy](#linking-strategy)
- [E. Dashboard Design](#e-dashboard-design)
- [F. Data Model](#f-data-model)
- [G. Integration Design (Phase 4, provisional)](#g-integration-design-phase-4-provisional)
- [H. Automation Design](#h-automation-design)
  - [H1. Levels](#h1-levels)
  - [H2. Commands](#h2-commands)
  - [H3. Agents](#h3-agents)
- [I. Implementation Plan](#i-implementation-plan)
- [J. Decision List](#j-decision-list)
  - [Details the Phase 1 plan must define](#details-the-phase-1-plan-must-define)
- [Testing approach](#testing-approach)
- [Risks](#risks)

## 0. Intent

A local, single-user engineering operating system with three parts:

1. **Obsidian vault**: the only source of truth for tasks, standups, decisions,
   knowledge, standards, upskilling and system rules. Plain Markdown with YAML
   frontmatter. Useful with Obsidian alone.
2. **Claude Code**: the workflow engine. Reads and writes the vault through a
   small set of commands and reuses the engineering workflow already installed.
3. **Web app**: dashboard, search, timeline and analytics over the vault. Its
   database is an index that can be dropped and rebuilt at any time.

Success means daily work (capture, tasks, standups, decisions, knowledge) runs
through the vault, the dashboard answers "what do I need to do, what is
blocked, what changed", and nothing is lost if the app or Claude Code is
removed.

### Confirmed decisions (2026-10-01)

| # | Decision | Choice |
|---|---|---|
| C1 | Vault | New vault, separate from the existing one. Old vault untouched; migration later. |
| C2 | Vault location | `D:\Second Brain` (`/mnt/d/Second Brain` in WSL), its own git repo, local only, no remote. |
| C3 | App writes | The app writes Markdown directly into the vault. The database is never the origin of a note. |
| C4 | Backend | Django + Django REST Framework + PostgreSQL. |
| C5 | Frontend | React + TypeScript + Vite + shadcn/ui, as a separate SPA against the DRF API. |
| C6 | Runtime | Docker + `docker-compose.yml`, configuration through `.env`. |
| C7 | Delivery | One phase at a time. Each phase: spec, plan, implement, review, test, approval. |
| C8 | Orchestration | Fable plans and delegates; specialist subagents implement, review and test. |
| C9 | Work tracking | beads (`bd`) in the app repo, one epic per phase. |

Confirmed 2026-10-05 (previously open as D1, D3, D9, D10):

| # | Decision | Choice |
|---|---|---|
| C10 (D1) | App login | Yes: one Django user, session login, CSRF enforced. |
| C11 (D3) | Vault git history | `/eod` makes one commit per day; the app never runs git. |
| C12 (D9) | First app-repo commit | An initial docs-only commit on `main`, then a feature branch per phase. |
| C13 (D10) | Timezone | `TZ=Asia/Manila` in `.env`. |

Confirmed 2026-10-05 during review of the Phase 1 plan
([`../plan/phase-1-foundation.md`](../plan/phase-1-foundation.md)):

| # | Decision | Choice |
|---|---|---|
| C14 (D2) | Obsidian Sync | Off for the new vault. |
| C15 | Build order around the mount spike | Only the Markdown and frontmatter parser may be built before the spike, in WSL with `uv`. The vault conformance checker imports that parser rather than re-implementing its rules. The writer and everything else wait for the spike. |
| C16 | Command tests | Headless `claude -p` tests against a temporary vault, behind an opt-in marker, run at task acceptance and at the final phase check. |
| C17 | App write endpoints | Generic create from template (task, project, decision, lesson), generic status change, and capture triage, in addition to capture and standup. |
| C18 | App user account | One Django user created by hand with `manage.py createsuperuser` and re-created by hand after any database rebuild. No user credentials in `.env`. This is a stated, deliberate exception to "the database holds no state of its own": the user account and sessions exist only in the database. `reindex` truncates only the index tables, never cascading into user or session tables. The app refuses to start with the `.env.example` placeholder secret key. Automated tests and the e2e stack create their own users; that step never applies to the real stack. |
| C19 | `project` value | Written by the writer and the commands as a wikilink, `project: "[[Project title]]"`. The indexer derives the slug from it and still accepts a plain slug typed by hand. Templates leave `project:` empty. |
| C20 | Generated ids | Within one operation that creates several notes, the generated `id` advances one second per note. |
| C21 | Renames and note handles | A rename is a delete plus an add, logged as a move when the `id` matches. The API looks notes up by path or by `id`. |
| C22 | Duplicate note names | Allowed in different folders. Ambiguous links resolve deterministically and are flagged "ambiguous". When the writer or a command writes a link to a stem that is not unique on disk, it writes the folder-qualified form `[[folder/Name]]`. Uniqueness checks read the filesystem, never the index. A create that collides with an existing name in the same folder, differing only by case, is still rejected. |
| C23 | Mounts | The rule is "no other host data path": repository source and read-only test fixtures may be bind-mounted for development and tests. |
| C24 | Index status | A dedicated Index Status page in Phase 1 navigation (last sync, counts, parse errors, missing and duplicate ids, ambiguous links, "Refresh index"). The Dashboard keeps a small summary that links to it. |
| C25 | Repository layout | Three independent top-level folders: `second-brain/` (vault source only: templates, vault README, init script, golden sample vault; the real vault stays at `D:\Second Brain`, outside the repo), `web-app/` (`backend/`, `dashboard/`, Compose files) and `claude-workflow/` (skill, commands, installer, tests; installed globally into `~/.claude`). Confirmed 2026-10-05. |
| C26 | Git from commands | A session never runs `git` directly. `/eod` commits through the fixed script `vault_git.py`, which refuses a vault with a remote, scans for secrets and writes the one daily commit (Phase 1 plan section 4.2). Supersedes the wording of C11 on how `/eod` commits, not who commits. |

---

## A. Environment Assessment

| Area | Finding |
|---|---|
| OS | Windows host, WSL2 Ubuntu 24.04. Projects on `D:` (`/mnt/d/Projects`), mounted through drvfs. |
| Tooling | Python 3.12, uv 0.9, Node 22, npm 10, git 2.43, bd 0.47, graphify 0.8. Missing in WSL: `gh`, `glab`, `psql`, `sqlite3`. |
| Docker | Docker Desktop is installed on Windows. **WSL integration is not enabled for this distro**, so `docker` fails inside WSL. Prerequisite for Phase 1. |
| App repo | `/mnt/d/Projects/second-brain-workflow`: empty, no commits, remote `git@github.com:kraaaam/second-brain-workflow.git`. |
| Claude Code config | `~/.claude/CLAUDE.md` (engineering instructions, mirrored with the Globe copy), `~/.claude/docs/` (9 standards docs), `settings.json` with `bd prime` hooks on SessionStart and PreCompact, a custom status line. |
| Agents | 12 user agents: solutions-architect, solutions-architect-reviewer, backend-engineer-python, backend-engineer, frontend-engineer, devops-cloud-engineer, qa-test-engineer, security-engineer, code-reviewer, technical-writer, incident-investigator, slides-designer. |
| Skills | engineer, cr-writing, pentest-triage, graphify, backend-agent, frontend-design, find-skills, plus plugin skills (superpowers, beads, code-review, feature-dev, figma, engineering). |
| MCP servers | Working: context7, serena, sequential-thinking, memory-bank, stitch, playwright. Present but unauthenticated: Atlassian, Figma, and others in the engineering plugin. Failing: GitHub plugin (bad auth header), supermemory, magic. None for Gmail, Calendar, Drive or GitLab. |
| Obsidian | Installed at `C:\Program Files\Obsidian`. One vault: `C:\Users\User\Documents\Obsidian Vault`, 154 notes, in active use. Structure under `Main/`: `00-Daily`, `01-Projects` (GIDA, Hawkeye, IPP, LoadUp), `02-Learnings`, `03-Workflows`, `99-Templates`, `Creds`. Templater installed; Bases, Sync, Daily notes and Templates core plugins on. Not a git repo. |
| Roadmap | `/mnt/d/Projects/Personal/career-roadmap`: `docs/00-mvp-4-month.md` (17 weeks from 2026-09-21 to 2027-01-17), `08-skills-matrix.md`, `11-progress-reviews.md`. |
| Claude usage data | `~/.claude/projects/**/*.jsonl` (166 MB, 18 project folders). Each assistant message carries model, input, output, cache read and cache write tokens, session id, cwd, timestamp and a sidechain flag. `~/.claude/stats-cache.json` holds daily aggregates. |
| Existing automation | `bd prime` hooks; status line script. No cron, no other dashboards, no databases. |

## B. Current-State Assessment

**Reuse as is**

- The `engineer` skill, the 12 agents and `~/.claude/docs/`. Together they
  already implement the brief's closed-loop workflow (sections 7 to 16), failure
  classification, review finding classification, the incident workflow and the
  document workflow. This project does not re-implement any of it.
- `cr-writing` for stakeholder documents; `technical-writer` for engineering
  documents.
- beads for cross-session tracking; context7 for library documentation.
- Session JSONL logs as the Phase 5 data source.
- The career-roadmap repository as the upskilling foundation.

**Missing (to build)**

- The new vault, its frontmatter conventions and templates.
- Vault commands for Claude Code (capture, triage, task, project, daily,
  standup, eod, decision, knowledge, and later ones).
- An "update Second Brain" step at the end of engineering work.
- The web app: indexer, vault writer, API, SPA.
- Integrations for Gmail, Calendar, Drive, Jira, GitLab, GitHub, Figma.
- Usage observability.

**Conflicts and constraints**

| Item | Impact | Handling |
|---|---|---|
| Old vault contains `Main/Creds` | Conflicts with "no credentials in Markdown" | Out of scope: the old vault is not indexed, versioned or modified. Follow-up for the user: move credentials to a password manager before any migration. The new vault never holds credentials; the indexer also skips any path listed in an ignore file. |
| drvfs gives WSL and Docker no file change events for edits made on Windows | A file watcher would miss Obsidian edits | The indexer polls and compares modification time and size, then hashes changed files. No watcher. |
| Docker WSL integration off | Compose stack cannot start | User enables it in Docker Desktop (Settings, Resources, WSL integration). First step of Phase 1. |
| Command name collisions (`/plan`, `/security-review`, `/code-review` already exist) | New commands could shadow built-ins | Engineering commands are not created; they map to existing ones (section H2). |
| `~/.claude/CLAUDE.md` is mirrored with the Globe copy | Edits there must be mirrored | This project adds a skill and commands only; it does not edit the mirrored files. If a later phase needs a line in the Skills section, that section is global-only by the mirror rule. |
| App repo has no commits and a public-capable remote | Notes must never reach GitHub | The vault is a separate repo with no remote. `.env` is gitignored. |

**Leave unchanged**

The old vault, `~/.claude/CLAUDE.md` and `~/.claude/docs/`, the existing agents
and skills, the status line, the career-roadmap repository, and all Strato
project repositories.

## C. Proposed Architecture

```text
 Gmail  Calendar  Drive  Jira  Figma  GitLab  GitHub        (Phase 4, read-only)
    \       |       |      |     |      |       /
     +------+-------+------+-----+------+------+
                          |
          +---------------+----------------+
          |                                |
          v                                v
   +-------------+                 +------------------+
   | CLAUDE CODE |                 | WEB APP (Docker) |
   | commands +  |                 |  frontend (Vite) |
   | engineer    |                 |  backend (DRF)   |
   | skill +     |                 |  indexer (poll)  |
   | agents      |                 |  db (PostgreSQL) |
   +------+------+                 +---+----------+---+
          | read / write               | read     | write through
          | Markdown                   | (scan)   | vault writer only
          v                            v          v
   +-----------------------------------------------------+
   |  OBSIDIAN VAULT   D:\Second Brain   (git, local)    |
   |  Markdown + YAML frontmatter: the source of truth   |
   +-----------------------------------------------------+
```

### Components

| Component | Responsibility | Depends on |
|---|---|---|
| Vault | Holds every note. Readable and editable with Obsidian alone. | Nothing |
| Claude Code commands | Create and update notes following the vault conventions; run the engineering workflow. | Vault, `second-brain` skill |
| `indexer` | Scans the vault, parses frontmatter and links, upserts index rows, removes rows for deleted files. | Vault (read), db |
| `vault writer` | The only code path in the app that writes files. Creates notes from templates and edits frontmatter or appends content. | Vault (write) |
| `api` | DRF endpoints for lists, detail, search, dashboard aggregates and write actions. | db, vault writer |
| `frontend` | React SPA. Never touches the vault or database directly. | api |
| `db` | PostgreSQL index and cache. Disposable. | Nothing |

The vault itself lives outside the repository. The repository holds three
independent components: `second-brain/` (the vault source that the init script
installs into a vault: seed templates, vault README, and the golden sample
vault), `claude-workflow/` (the `second-brain` skill, the commands and their
install script) and `web-app/` (the backend with `indexer`, `vault writer` and
`api`, the dashboard frontend, and the Compose file). The Phase 1 plan, section
6, shows the full tree.

### Data flows

- **Read**: vault file, indexer, PostgreSQL, API, SPA.
- **Write from the app**: SPA, API, vault writer writes the file, indexer
  re-indexes that one file, API returns the indexed note. If the file write
  fails, nothing is indexed and the API returns the error.
- **Write from Obsidian or Claude Code**: the file changes on disk; the next
  indexer poll picks it up. The SPA also has a "Refresh index" action.
- **Rebuild**: `manage.py reindex` truncates the index tables (`Note`, `Link`,
  `Tag` and their join table, never with `CASCADE`) and rescans. The result must
  be identical to the incremental state. This is the invariant that proves the
  database is not a competing source of truth, and it has a test.
- **Stated exception (C18)**: the Django user account and sessions exist only in
  the database. They are not rebuilt by `reindex` (which leaves them alone); after
  the database itself is dropped, the user is re-created by hand with
  `manage.py createsuperuser`.

### Write safety

- Writes are confined to the vault root; resolved paths outside it are rejected.
- New files are written to a temporary file in the same directory, then renamed.
  Temporary files are dot-prefixed and do not end in `.md`, so neither Obsidian
  nor the indexer picks them up.
- Edits to an existing file carry the content hash the client last saw. The
  writer re-reads and hashes the file **from disk** immediately before the
  rename; it never compares against the indexed hash, which can lag by a poll
  interval. A mismatch returns `409 Conflict` instead of overwriting an
  Obsidian edit.
- Residual risk, accepted: if a note is open in Obsidian with unsaved changes,
  Obsidian's autosave can overwrite an app write made in the same moment. App
  writes are small and the vault is under git, so the loss is recoverable.
- Notes whose YAML is malformed are indexed with an error flag and shown as
  such; the writer refuses to edit them.
- File names are sanitised for Windows-illegal characters, and a create that
  would collide with an existing name differing only by case is rejected.
- Frontmatter edits use a round-trip YAML writer so unknown keys, key order and
  the note body are preserved.
- The app never deletes vault files. "Cancelled" and "archived" are statuses.
- The app never runs git in the vault. Vault commits are made by the `/eod`
  command or by hand (decision D3).

### Runtime topology (Docker Compose)

| Service | Image / command | Mounts | Ports (host) |
|---|---|---|---|
| `db` | PostgreSQL | named volume | none published by default |
| `backend` | Django + DRF | `${VAULT_PATH}:/vault` read-write | `127.0.0.1:8000` |
| `indexer` | same image, `manage.py sync_vault --watch` (poll loop) | `${VAULT_PATH}:/vault` read-only | none |
| `frontend` | Vite dev server | source bind mount, named volume for `node_modules` | `127.0.0.1:5173` |
| `test` (profile `test`) | same image as `backend`, runs the backend test suite | source bind mount, test fixtures read-only; **no vault mount** | none |

End-to-end tests and the final rebuild check run in a separate Compose project,
`sbw-e2e`, with its own database volume, ports and a copy of a vault; it never
mounts the real vault. Details are in the Phase 1 plan.

The Vite dev server proxies `/api` to `backend`, so the SPA and the API are
same-origin in the browser. That removes CORS entirely and keeps session and
CSRF cookies simple. The browser always uses `http://localhost:5173`.

The app repo is on drvfs (`/mnt/d`), which delivers no file events into
containers. Vite and Django autoreload therefore run in polling mode, and
`node_modules` lives in a named volume rather than on the bind mount.

All services take `TZ` from `.env` (decision D10), so "today", "overdue" and
daily note names match the user's local date rather than UTC.

Phase 5 adds a read-only mount of `~/.claude/projects` to `indexer`. No Celery,
Redis or message broker: a poll loop is enough for one user (YAGNI). A
production-style build (static SPA behind the Django container or nginx) is not
needed for a localhost tool and is left out until there is a reason.

### Security boundaries

| Boundary | Rule |
|---|---|
| Network | All published ports bind to `127.0.0.1`. `ALLOWED_HOSTS` lists only local names. No CORS: the API is reached through the Vite proxy on the same origin. |
| Authentication | Single user, Django session login, CSRF enforced (decision D1). The API can write files, so it is not left open to any local web page. |
| Filesystem | Backend has read-write access to the vault only. Indexer is read-only. No other host data path is mounted in Phases 1 to 4; repository source and read-only test fixtures may be bind-mounted for development and tests (C23). Backend tests run in a service with no vault mount. |
| Secrets | `.env` only, gitignored, with a committed `.env.example`. No secret in the vault, the repo, the database dumps or the UI. Integration tokens (Phase 4) follow the same rule. |
| External content | Email, ticket, document and web content is stored and displayed as data. It is never interpreted as instructions by a command, and it cannot trigger a write on its own. |
| Consequential actions | Anything in the APPROVE column of section H needs explicit approval each time. |

## D. Vault Design

### Folder structure

Phase 1 creates only what Phase 1 uses. Later folders are created by the phase
that needs them.

```text
Second Brain/
├── 00-Inbox/                      Phase 1
├── 01-Daily/2026/                 Phase 1
├── 02-Work/
│   ├── Projects/                  Phase 1
│   ├── Tasks/                     Phase 1
│   ├── Tickets/ Meetings/         Phase 4
│   ├── Incidents/                 Phase 2
│   └── Follow-ups/                when needed
├── 03-Engineering/                Phase 2
├── 04-Documents/                  Phase 2
├── 05-Knowledge/
│   ├── Decisions/                 Phase 1
│   ├── Lessons/                   Phase 1
│   └── Concepts/ Patterns/ References/   when needed
├── 06-Upskilling/                 Phase 3
├── 07-External-Context/           Phase 4
├── 08-System/
│   ├── Templates/                 Phase 1
│   ├── Rules/ Preferences/ Corrections/ Workflow/   Phase 6 (earlier if needed)
└── 99-Archive/                    when needed
```

### Frontmatter

Common keys, all lower case, all optional except `type`:

```yaml
---
type: task            # task | project | daily | decision | lesson | capture (Phase 1)
id: 20261001153200    # creation timestamp; survives renames
status: in-progress
priority: high        # low | medium | high
project: "[[LoadUp]]" # wikilink to a project note (C19); a plain slug is also accepted
created: 2026-10-01
due: 2026-10-05
tags: [engineering, backend]
---
```

- Task statuses: `inbox`, `planned`, `in-progress`, `blocked`, `review`, `done`,
  `cancelled`.
- Type-specific keys are added only when a type needs them (for example
  `blocked_by` on a task, `decided` on a decision).
- External references (Phase 4) use the brief's five keys: `external_provider`,
  `external_object_id`, `external_object_type`, `external_url`, `last_synced`.
- Unknown keys are preserved and indexed as-is; adding a key never needs a
  migration.
- There is no maintained `updated` key. Obsidian would never set it, so it
  would be unreliable. "Last changed" comes from the file's modification time.

### Note identity and naming

- File name is the human title (`Investigate missing OTP email.md`). Daily notes
  are `YYYY-MM-DD.md`.
- **The index is keyed on the vault-relative path.** That is the only identity
  that every note is guaranteed to have, including notes created by hand in
  Obsidian.
- `id` in frontmatter is an indexed attribute, not a unique key. It gives the
  API a stable handle for notes that have one: notes can be looked up by path or
  by `id` (C21). A rename is a delete plus an add; when the same `id` appears at
  a new path in one scan, it is logged as a move.
- Missing and duplicate ids (for example from Obsidian's "Make a copy") are
  reported on the Index Status page (C24). They are never an indexing failure.
- Notes with the same name may exist in different folders (C22). A create that
  collides with an existing name in the same folder, differing only by case, is
  rejected.
- Notes without frontmatter are still indexed, with `type: note`.

### Ignored paths

The indexer skips `.obsidian/`, `.git/`, `.trash/`, `08-System/Templates/` and
dot-prefixed temporary files by default, plus anything listed in a vault-level
ignore file. Templates carry `type: task` and similar, so without this they
would appear as real tasks.

### Templates (Phase 1)

`08-System/Templates/`: `task.md`, `project.md`, `daily.md`, `decision.md`,
`lesson.md`, `capture.md`. Plain Markdown using only the placeholders that
Obsidian's core Templates plugin understands (`{{title}}`, `{{date}}`,
`{{time}}` and their format variants, so `id` is written as a formatted date).
The vault writer and the Claude Code commands implement that same subset, so a
note has the same shape whichever of the three created it. Phase 1 verifies the
placeholder behaviour in Obsidian before the templates are fixed.

The daily template is the brief's standup shape: Done, Today, Blockers,
Decisions / Updates, Follow-ups, Related Tasks / Projects.

### Linking strategy

- Relationships are Obsidian wikilinks (`[[Note title]]`) in the body or in
  frontmatter list values, so the graph works in Obsidian without the app.
- `project` is written as a wikilink to the project note (C19); the indexer
  derives a slug from it, or takes a plain slug typed by hand, and resolves the
  slug to the project note.
- Links written by the writer or a command to a stem that is not unique on disk
  use the folder-qualified form `[[folder/Name]]` (C22).
- The indexer stores each link's normalised target title. Links are resolved to
  notes at query time, not at index time, so creating or renaming a target
  later needs no re-indexing of the notes that point to it. Unresolved links
  are kept and shown as such; they are not errors.
- Resolution rules are fixed in the Phase 1 plan: case-insensitive match,
  `[[A|alias]]`, `[[A#heading]]`, `![[embed]]`, and two notes sharing a base
  name (resolved deterministically and flagged "ambiguous", C22).
- Automatic linking by Claude Code is limited to high-confidence cases (same
  project, explicit mention). Anything else is suggested.

## E. Dashboard Design

Navigation grows by phase; a page appears when its data exists.

| Page | Phase | Content |
|---|---|---|
| Dashboard | 1 | Today's tasks, in progress, blocked, overdue, today's standup, recent activity, active projects, inbox count, a small index status summary linking to Index Status |
| Tasks | 1 | List and status board; filter by project, status, priority, due; create, change status |
| Projects | 1 | Project list; per project: open tasks, decisions, recent notes |
| Standups | 1 | Daily notes by date; start today's standup with unfinished work carried forward |
| Inbox | 1 | Captures awaiting triage; quick capture |
| Knowledge, Decisions | 1 | Browse and read |
| Search | 1 | Full-text search over the vault; every result shows its source |
| Index Status | 1 | Last sync, counts, parse errors, missing ids, duplicate ids, ambiguous links; "Refresh index" action (C24) |
| Architecture, Incidents, Documents, Engineering Standards | 2 | Browse, create from template |
| Upskilling | 3 | Roadmap week, skills, gaps with evidence |
| Tickets, Calendar, Integrations | 4 | External references and integration status |
| Timeline | 4 | Per-project history across notes and external objects |
| Claude Usage | 5 | Tokens, estimated cost, sessions, models, agents; 1, 7, 30, 90 day views |
| System | 6 | Rules, preferences, corrections, suggestions awaiting approval |

Quick actions in Phase 1: Capture Thought, Create Task, Start Standup, Record
Decision, Add Knowledge. Others arrive with their phase.

Display rules: a value that is not available shows `N/A`; an estimated value is
labelled `Estimated`; every search and timeline row names its source.

## F. Data Model

Phase 1 has three index tables. Tasks, projects, decisions and standups are
notes filtered by `type`; they do not get their own tables.

| Entity | Fields | Notes |
|---|---|---|
| `Note` | `path` (unique key), `note_id` (frontmatter `id`, indexed, not unique, nullable), `type`, `title`, `status`, `priority`, `project`, `due`, `created`, `frontmatter` (JSON), `body`, `content_hash`, `file_mtime`, `file_size`, `parse_error`, `search_vector` | Promoted columns exist only for fields the UI filters on. Everything else stays in `frontmatter`. |
| `Link` | `source` (Note), `target_title` (normalised) | No foreign key to the target; resolved by join at query time. |
| `Tag` | `name`, many-to-many with `Note` | |

Search uses a generated, stored `search_vector` with PostgreSQL's `simple`
text search configuration, plus trigram matching on titles. The `english`
configuration would stem and drop tokens, which mangles ticket keys,
identifiers and paths. Both are deterministic, so they survive a rebuild
unchanged.

Later additions, each justified by its phase:

| Entity | Phase | Why a table |
|---|---|---|
| `ExternalObject` | 4 | Cached reference to a ticket, meeting, MR or file, for timeline and search. Rebuildable from the provider. |
| `IntegrationStatus` | 4 | Last sync time and last error per provider. |
| `TokenUsage` | 5 | One row per assistant message from the session logs. Rebuildable only within Claude Code's log retention window; see decision D7. |

Phase 6 suggestions are Markdown notes (decision D6), not a table.

Everything else in the brief's entity list (Standup, Meeting, Decision,
Incident, Knowledge, Skill, Correction, Rule, and so on) is a Markdown note with
a `type`.

## G. Integration Design (Phase 4, provisional)

The integration path is the largest open decision (D5): Claude Code MCP
connectors, Django-side API clients, or both. The table shows the recommended
split, which is to use connectors for on-demand context inside Claude Code and
Django-side read-only clients only for what the dashboard must show unattended.

| Source | Authentication | Permissions | Data | Direction | Frequency | Storage | Failure handling |
|---|---|---|---|---|---|---|---|
| Google Calendar | OAuth, read-only scope | READ | Today's and upcoming meetings | In | Poll, minutes | `ExternalObject` cache | Show last synced time; dashboard still loads |
| Gmail | OAuth, read-only scope | READ | Subject, sender, link for flagged or matching mail; no bodies stored by default | In | On demand, then poll | Reference only | Same |
| Google Drive | OAuth, read-only scope | READ | File title, link, modified time | In | On demand | Reference only | Same |
| Jira | API token or Atlassian connector | READ | Assigned issues: key, title, status, link | In | Poll | `ExternalObject` cache | Same |
| GitLab | Personal access token, `read_api` | READ | MRs, pipelines for linked issues | In | Poll | `ExternalObject` cache | Same |
| GitHub | Fine-grained token, read-only | READ | PRs, checks | In | Poll | `ExternalObject` cache | Same |
| Figma | Figma connector | READ | File link and title | In | On demand | Reference only | Same |
| CI/CD, cloud, monitoring | Through GitLab or GitHub first | READ | Pipeline and deployment status | In | Poll | `ExternalObject` cache | Same |

Common rules: read-only until a later, separately approved change; tokens in
`.env`, never in the vault; external content is data, not instructions; a
provider outage degrades one panel and never blocks the vault or the rest of
the dashboard; every cached object carries `last_synced`.

Work accounts (Strato Google Workspace, Jira, GitLab) may be subject to company
policy on third-party access. That must be confirmed before Phase 4 design.

## H. Automation Design

### H1. Levels

| AUTO | SUGGEST | APPROVE |
|---|---|---|
| Indexing and re-indexing | Triage classification below high confidence | Any external write (email, calendar, Jira, GitLab, GitHub, Drive) |
| Formatting a note from its template | Links between notes below high confidence | CI/CD execution, production changes |
| Carrying unfinished tasks into today's standup draft | New tasks from email, meetings or tickets | Deleting or moving vault notes |
| Linking a note to its stated project | Skill gaps and learning topics | Promoting a correction to a permanent rule |
| Usage aggregation | Workflow or standards changes | Changing vault structure or frontmatter conventions |
| | Document improvements | Marking a task `done` without evidence |
| Triage classification at high confidence | | Major architecture or security-sensitive changes |

### H2. Commands

New vault commands are thin: each loads the `second-brain` skill, which holds
the vault path, conventions and templates in one place. Engineering commands
are not duplicated.

| Brief command | Handling | Phase |
|---|---|---|
| `/capture`, `/triage` | New | 1 |
| `/task`, `/project` | New | 1 |
| `/daily`, `/standup`, `/eod` | New | 1 |
| `/decision`, `/knowledge` | New | 1 |
| `/weekly-review` | New | 2 |
| `/incident`, `/document`, `/architecture`, `/architecture-review` | Existing `/engineer` workflow, with vault output added | 2 |
| `/standards`, `/recommend`, `/engineering-review` | New, thin | 2 |
| `/plan`, `/implement`, `/test`, `/review-code`, `/security-review` | Existing `/engineer`, `/code-review`, `/security-review`. Not recreated. | n/a |
| `/ticket` | New | 4 |
| `/integrations` | New | 4 |
| `/learn`, `/upskill` | New | 3 |
| `/usage` | New | 5 |
| `/improve` | New | 6 |

Commands live in the app repo under `claude-workflow/` and are installed into
`~/.claude/` by a small install script, so they are versioned and work from any
project directory.

### H3. Agents

No new agents. The existing 12 cover the brief's list (Planner, Backend,
Frontend, Database, Testing, Security, Architecture, Documentation, Code
Reviewer). Vault commands run in the main session; delegation is used for
building the app, not for writing a note.

## I. Implementation Plan

See [`../plan/master-plan.md`](../plan/master-plan.md). Summary:

| Phase | Goal |
|---|---|
| 1 Foundation | Vault, conventions, Phase 1 commands, Compose stack, indexer, writer, API, basic dashboard |
| 2 Engineering | Architecture, incidents, standards, documents, templates, weekly review |
| 3 Upskilling | Skills, learning loop, existing 4-month roadmap |
| 4 External context | Read-only integrations, tickets, calendar, timeline |
| 5 Claude observability | Token usage, estimated cost, trends |
| 6 Intelligent automation | Suggestions, relationship detection, self-improvement loop |

## J. Decision List

Confirmed decisions are in section 0 (D1, D2, D3, D9 and D10 were confirmed on
2026-10-05 and moved there). Open ones:

| # | DECISION REQUIRED | Recommendation | Needed by |
|---|---|---|---|
| D4 | Phase 3: link to `career-roadmap/docs` from the vault, or import the roadmap and skills matrix into the vault? | Import the skills matrix and weekly checklist into the vault (it must be the source of truth for upskilling); keep long-form reference docs in the career-roadmap repo and link to them. | Phase 3 design |
| D5 | Phase 4: integration path (Claude Code connectors, Django-side clients, or both) and which accounts (work or personal). Is third-party access to Strato accounts permitted? | Both, split as in section G. Needs the policy answer first. | Phase 4 design |
| D6 | Phase 6: where do pending suggestions live? | As Markdown in `00-Inbox` with `type: suggestion`, so even this is rebuildable and no table holds original state. | Phase 6 design |
| D7 | Phase 5: Claude Code prunes old session logs, so `TokenUsage` rows older than the retention window cannot be rebuilt. This would be the second stated exception to "the database holds no state of its own", after the user account and sessions (C18). Accept that as a stated exception, or limit usage views to the retention window? | Accept it as an explicit, documented exception for this one table, and also write a monthly usage summary note into `08-System/Usage/` so the long-term totals live in the vault. Per-session detail older than the window is lost on a rebuild. | Phase 5 design |
| D8 | When and how to migrate notes from the old vault | Not before Phase 2 is in use. Project by project, with `Creds` excluded. | After Phase 2 |
| D11 | Keep the app repo on `D:` (drvfs) or move it to the WSL filesystem? Only the vault must be on a Windows drive. On drvfs, hot reload needs polling and dependency installs are slower. | Keep it at `/mnt/d/Projects/second-brain-workflow` as requested, with polling and a named volume for `node_modules`. Revisit only if the Phase 1 spike shows it is painful. | Phase 1 spike |

### Details the Phase 1 plan must define

These are not user decisions, but the task-level plan is incomplete without
them: the `project` slug rule; carry-forward semantics for standups (task
status versus unchecked checkboxes in the previous daily note); the status
vocabulary for non-task types; how the writer locates a heading for "append to
section"; file name sanitising rules; vault git configuration
(`core.autocrlf=false`, `core.filemode=false`, ignoring
`.obsidian/workspace*.json`); the poll interval and a full-scan time budget;
wikilink resolution rules.

## Testing approach

- **Backend**: pytest and pytest-django. Vault fixtures are temporary
  directories of small Markdown files. Covered: frontmatter parsing including
  malformed YAML, incremental sync (add, edit, rename, delete), the rebuild
  invariant, writer path confinement, atomic write, conflict detection,
  round-trip preservation of unknown keys and body, API authentication.
- **Frontend**: Vitest and React Testing Library for components and data hooks.
- **End to end**: Playwright for a handful of flows: capture then triage to a
  task, create a task and move it to done, start a standup with carry-forward,
  search.
- **Commands**: each vault command is exercised against a temporary vault and
  its output is checked against the template shape, through headless
  `claude -p` runs behind an opt-in marker (C16).

## Risks

| Risk | Mitigation |
|---|---|
| The system becomes more work than the notes it manages | Phase 1 must be useful with Obsidian and commands alone; each phase is approved only after the previous one is in daily use. |
| App and Obsidian edit the same file | Hash check and `409` on conflict; atomic writes; app writes are small and targeted. |
| Bind-mounting a Windows path into Docker Desktop containers behaves differently from a native filesystem | A spike at the very start of Phase 1, before anything is built on the mount, measures full-scan time, renaming over a file Obsidian has open, ownership and permissions of created files, and handling of the space in `VAULT_PATH`. The vault stays on `D:`; if the spike fails, the design returns to planning rather than moving the vault. |
| Frontmatter conventions drift between Obsidian, commands and app | One schema description in the `second-brain` skill; templates are the single shape; indexer tolerates unknown and missing keys. |
| Scope creep across 6 phases | Per-phase approval gate; later phases are outlines until reached. |
| Work-account integration blocked by policy | Asked before Phase 4 design (D5); Phases 1 to 3 and 5 do not depend on it. |
