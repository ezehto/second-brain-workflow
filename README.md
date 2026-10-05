# second-brain-workflow

An Obsidian-first engineering second brain: an Obsidian vault as the source of
truth, Claude Code commands that read and write it, and a web dashboard that
indexes it.

## Contents

- [What this is](#what-this-is)
- [Status](#status)
- [Repository layout](#repository-layout)
- [The commands](#the-commands)
- [Running the tests](#running-the-tests)
- [Documentation](#documentation)
- [Working rules](#working-rules)

## What this is

Three independent components that share one set of conventions:

| Component | Folder | Purpose |
|---|---|---|
| Vault source | `second-brain/` | Templates, the vault README, the script that creates a vault, and a golden sample vault used as a test fixture |
| Claude Code workflow | `claude-workflow/` | The `second-brain` skill, nine slash commands, the installer, and their tests |
| Web dashboard | `web-app/` | Django and PostgreSQL backend that indexes the vault, and a React dashboard (in progress) |

The real vault lives outside this repository, at `D:\Second Brain`
(`/mnt/d/Second Brain`), in its own local-only git repository. It is never
pushed. The database is only an index: it can be dropped and rebuilt from the
vault at any time.

## Status

Phase 1 (Foundation) is in progress on the `phase-1-foundation` branch.

| Area | State |
|---|---|
| Vault templates, conventions, init script, golden sample vault | Done |
| Markdown and frontmatter parser, vault conformance checker | Done |
| `second-brain` skill and the nine commands | Written, reviewed and tested; not yet installed into `~/.claude` |
| Docker Compose stack, indexer, vault writer, API, dashboard pages | Not started |
| Dashboard UI prototype | Design validation only, not in this repository |

Task tracking is in Beads: run `bd ready` for the next unblocked task.

## Repository layout

```text
second-brain/        vault source: templates, vault-readme.md, scripts/init_vault.py, fixtures, tests
claude-workflow/     skills/second-brain (SKILL.md, reference/, scripts/vault_git.py),
                     commands/*.md, install.sh, tests (offline and live command scenarios)
web-app/             backend/ (parser and conventions under vault/, tests), scripts/spike
docs/plan/           master-plan.md and the Phase 1 task plan
docs/specs/          design specification
docs/spikes/         mount spike procedure and results
docs/reviews/        workflow review and findings
```

Each component is its own `uv` project. A component may read another's files
in tests by relative path; it never keeps its own files or configuration in
another component's folder or in the vault.

## The commands

All nine load the `second-brain` skill, which holds the vault path, the
conventions and the templates in one place.

| Command | What it does |
|---|---|
| `/capture` | Saves a thought to the inbox as a capture note |
| `/triage` | Classifies inbox captures and, after approval, turns them into task, decision, lesson or project notes |
| `/task`, `/project` | Create a task or project note from its template |
| `/decision`, `/knowledge` | Record a decision or a lesson |
| `/daily` | Ensures today's daily note exists, with unfinished work carried forward |
| `/standup` | Ensures today's note, appends what you give it, and prints the standup |
| `/eod` | Appends what was done, offers status changes, and commits the day to the vault's git repository |

A session never runs `git` directly. The only git surface is
`claude-workflow/skills/second-brain/scripts/vault_git.py`, which exposes a
fixed set of verbs and refuses a vault that has a remote.

## Running the tests

Each component runs its own suite with `uv`:

```bash
cd second-brain && uv run pytest tests -q
cd web-app/backend && uv run pytest tests -q
cd claude-workflow && uv run pytest tests -q
```

The `claude-workflow` suite excludes the live command scenarios by default.
They start real headless Claude Code sessions against a temporary vault, take
several minutes and cost money, so they are opt-in:

```bash
cd claude-workflow
SB_COMMANDS_MODEL=sonnet uv run pytest tests/commands -m commands -q -rf
```

## Documentation

- [`docs/plan/master-plan.md`](docs/plan/master-plan.md): the six phases and how each one runs.
- [`docs/specs/2026-10-01-second-brain-design.md`](docs/specs/2026-10-01-second-brain-design.md): architecture, vault design, data model, decisions.
- [`docs/plan/phase-1-foundation.md`](docs/plan/phase-1-foundation.md): the Phase 1 task plan.
- [`docs/spikes/phase-1-mount-spike.md`](docs/spikes/phase-1-mount-spike.md): mount measurements and the open Obsidian checks.
- [`docs/reviews/2026-10-06-workflow-review.md`](docs/reviews/2026-10-06-workflow-review.md): findings on the development workflow and the decisions waiting for an answer.
- [`CLAUDE.md`](CLAUDE.md): rules for Claude Code sessions working in this repository.

## Working rules

- The vault is the source of truth; nothing important lives only in the database.
- All application writes to the vault go through the vault writer.
- The old vault at `C:\Users\User\Documents\Obsidian Vault` is never touched.
- No secrets in the vault, the repository or the UI. Configuration comes from `.env`.
- One phase at a time; a phase starts only after the previous one is approved.
- Commit messages are a single imperative line.
