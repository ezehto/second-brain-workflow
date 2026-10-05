# Conventions

Audience: a Claude Code session writing or reading vault notes. Source: plan
sections 2.3, 2.9, 2.10 and 3.2, and design section D. This file is the single list of
folders and statuses; the other reference files must agree with it.

## Contents

- [Vault path](#vault-path)
- [Folders](#folders)
- [Status vocabulary](#status-vocabulary)
- [Frontmatter keys](#frontmatter-keys)
- [Type](#type)
- [Tags](#tags)
- [Dates](#dates)
- [Dates given to a command](#dates-given-to-a-command)
- [Defaults](#defaults)
- [Ignored paths](#ignored-paths)
- [Vault git](#vault-git)
- [Known limits](#known-limits)

## Vault path

The `vault` line of the `env` verb, see [../SKILL.md](../SKILL.md#running-tools). The old vault at
`/mnt/c/Users/User/Documents/Obsidian Vault` is never read or written.

## Folders

Phase 1 creates only these folders. Later phases add the others.

| Folder | Holds |
|---|---|
| `00-Inbox` | Captures. Also the default location for new notes made in Obsidian. |
| `01-Daily` | Daily notes, in a year folder: `01-Daily/YYYY/YYYY-MM-DD.md`. |
| `02-Work/Projects` | Project notes. |
| `02-Work/Tasks` | Task notes. |
| `05-Knowledge/Decisions` | Decision notes. |
| `05-Knowledge/Lessons` | Lesson notes. |
| `08-System/Templates` | The six templates. Read at run time by every creator. |

## Status vocabulary

Accept only a status from the note's own type. A note of type `daily` has no
`status` key. A note has type `note`, with no enforced status, only when it has
no frontmatter, malformed frontmatter or no usable string `type`. Any other
`type` value is kept as written (see [Type](#type)), never mapped to `note`, and
has no status vocabulary.

| Type | Statuses | Default on create |
|---|---|---|
| `task` | `inbox`, `planned`, `in-progress`, `blocked`, `review`, `done`, `cancelled` | `planned` |
| `project` | `active`, `paused`, `done`, `archived` | `active` |
| `decision` | `proposed`, `accepted`, `superseded`, `rejected` | `proposed` |
| `lesson` | `active`, `archived` | `active` |
| `capture` | `inbox`, `triaged`, `dismissed` | `inbox` |

Nothing is deleted. `cancelled`, `archived` and `dismissed` replace deletion.

## Frontmatter keys

All keys are lower case. Only `type` is required. Unknown keys are preserved.

| Key | Meaning |
|---|---|
| `type` | The known values are `task`, `project`, `daily`, `decision`, `lesson` and `capture`. Any other value is kept, see [Type](#type). |
| `id` | Creation timestamp written as `{{date:YYYYMMDDHHmmss}}`. YAML reads it as an integer. It survives renames. |
| `status` | From the vocabulary above |
| `priority` | `low`, `medium` or `high` (task) |
| `project` | A wikilink to a project note, see [links.md](links.md#project-values-and-slugs) |
| `created` | `YYYY-MM-DD` |
| `due` | `YYYY-MM-DD` (task) |
| `tags` | A list |

Keys that tools set only when needed:

| Key | On | Set when |
|---|---|---|
| `project` | task, decision, lesson | a project is given; written as a wikilink |
| `blocked_by` | task | the task is blocked |
| `decided` | decision | status becomes `accepted` |
| `classification` | capture | triage classifies it; one of ten values: `thought`, `task`, `ticket`, `architecture-idea`, `learning-topic`, `decision`, `question`, `note`, `problem`, `project`, see [triage.md](triage.md#classification-and-what-it-becomes) |
| `triaged_to` | capture | triage converts it; written as `"[[Target note]]"`, or the folder-qualified form when the stem is not unique, see [links.md](links.md#emitted-links) |

There is no `updated` key. "Last changed" comes from the file's modification
time.

## Type

| Frontmatter | Type |
|---|---|
| No frontmatter, malformed frontmatter, no `type` key, or `type` null, empty or not a string | `note` |
| A string | The string trimmed and lower-cased (`Task ` is `task`). Known types get their vocabulary. Any other value is kept as written, never mapped to `note`. |

An explicit `type: note` is the generic type, not an unknown type.
Keeping an unknown type visible lets the user find and fix it.

## Tags

- **Inline tags** are found in the body only: not in frontmatter, code regions
  (see [links.md](links.md#code-regions)), or the whole text of every wikilink and embed
  (`[[...]]`, `![[...]]`). So `[[A#Heading]]`, `[[A#^block]]` and `[[#H]]` never
  produce tags.
- An inline tag is `#` at the start of a line or directly after whitespace,
  followed by one or more tag characters: Unicode letters, combining marks, decimal digits, `_`, `-` and
  `/`. It ends at the first other character. So `# Heading` (space after `#`),
  `a#b` and `http://x/#frag` are not tags.
- A token is a tag only if it has at least one character that is not a digit and
  not `/`. `#1984` and `#2026/10` are not tags. `#y1984` and `#v2` are.
- **Nested tags:** `/` is kept (`#eng/backend` is stored as `eng/backend`).
  Parents are not added as separate tags. Every trailing `/` is stripped (`#eng/`
  and `#eng//` become `eng`).
- **Frontmatter `tags`:** a YAML list (each item converted to a string) or one
  string split on commas. Each item is trimmed and one leading `#` is removed.
  The result must be a valid tag token as above, so an item with internal
  whitespace or a numeric-only item such as `2024` is dropped. Only the `tags`
  key is read.
- Every tag is NFC-normalised and lower-cased. `#Eng` and `#eng` are one tag.
  A note's tags are de-duplicated.

## Dates

`due`, `created` and `decided` are valid when they are a YAML date, a YAML
timestamp (its calendar date as written, no timezone conversion), or a string
that is exactly `YYYY-MM-DD` and a real calendar date. Anything else is invalid.
An invalid `due` behaves like no due date everywhere, including carry-forward.
Write dates as `YYYY-MM-DD`.

## Dates given to a command

A date given to a command (for example `/task ... due:<date>`): the value
written is always `YYYY-MM-DD`. That form is accepted as given. A relative
expression (`tomorrow`, `friday`, `next week`) is resolved against today's date
from `today` (see [../SKILL.md](../SKILL.md#running-tools)), written as `YYYY-MM-DD`, and reported back in the
output. `friday` means the next Friday strictly after today. An expression with
more than one reasonable reading is not guessed: ask the user.

## Defaults

| Topic | Rule |
|---|---|
| Note title | The file name stem. |
| Note identity | The vault-relative path. `id` is a lookup handle, not a unique key. |
| Frontmatter | The file starts, after an optional BOM, with a line `---` and ends at the next line `---` or `...`. |
| Line endings | Keep a file's existing LF or CRLF and its BOM. |
| Templates | Read from `08-System/Templates` in the vault. |

## Ignored paths

`stem` applies the ignore rules, so a session never decides by hand what is a
note. This list is for understanding. These are not notes: any path segment that starts with `.` (covers `.obsidian`,
`.git`, `.trash` and writer temp files), `08-System/Templates`, files that do
not end in `.md`, and anything listed in `<vault>/.sbignore`. `.sbignore` has one vault-relative
glob per line, `#` comments, and a trailing `/` means a directory. Do not treat a
template as a real task or decision.

## Vault git

The vault is its own local git repo on branch `main`, with no remote. The vault init script (one initial commit) and `/eod` are the only git writers.
A session never runs `git` itself. `/eod` uses a fixed script, see
[../SKILL.md](../SKILL.md#git-and-eod).

## Known limits

Claude Code limits that no command text can prevent: argument text that
begins with another slash-command name loads that command too (`/capture /daily
was late`), and `${CLAUDE_...}` placeholders in argument text are substituted.
