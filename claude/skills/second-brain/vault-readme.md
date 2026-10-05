# Second Brain

This is an Obsidian vault of Markdown notes with YAML frontmatter. The notes are
the source of truth. A dashboard and Claude Code commands read and write them,
but they keep no state that is not here.

Audience: the vault's owner, opening it in Obsidian.

## Contents

- [Folders](#folders)
- [Note types](#note-types)
- [Templates](#templates)
- [Ground rules](#ground-rules)

## Folders

| Folder | Holds |
|---|---|
| `00-Inbox` | Captures waiting for triage |
| `01-Daily` | Daily notes, one per day, in year folders |
| `02-Work/Projects` | Project notes |
| `02-Work/Tasks` | Task notes |
| `05-Knowledge/Decisions` | Decision notes |
| `05-Knowledge/Lessons` | Lesson notes |
| `08-System/Templates` | The six note templates |

More folders are added when a later phase needs them.

## Note types

The `type` key in a note's frontmatter says what it is. The `status` key says
where it stands.

| Type | Statuses |
|---|---|
| `task` | `inbox`, `planned`, `in-progress`, `blocked`, `review`, `done`, `cancelled` |
| `project` | `active`, `paused`, `done`, `archived` |
| `decision` | `proposed`, `accepted`, `superseded`, `rejected` |
| `lesson` | `active`, `archived` |
| `capture` | `inbox`, `triaged`, `dismissed` |
| `daily` | no status |

Nothing is deleted. Use `cancelled`, `archived` or `dismissed` instead.

## Templates

`08-System/Templates` holds the templates. Edit them here. Obsidian, the
dashboard and the Claude Code commands all read this folder, so an edit changes
the shape of every new note. Templates use only `{{title}}`, `{{date}}`,
`{{time}}` and their format forms.

## Ground rules

- The file name is the note's title.
- Link notes with `[[Note title]]`. Write `project` as `"[[Project title]]"`.
- Do not add a git remote and do not sync this vault. Notes stay on this
  machine. The only commits come from the vault init script and `/eod`.
- Files and folders that start with a dot are hidden from the index.
