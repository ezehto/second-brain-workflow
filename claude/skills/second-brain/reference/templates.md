# Templates

Audience: a Claude Code session rendering a template. Source: plan sections
2.9, 3.1, 3.2 and 3.3.

## Contents

- [Where templates come from](#where-templates-come-from)
- [Placeholder subset](#placeholder-subset)
- [The six templates](#the-six-templates)
- [Keys set by tools](#keys-set-by-tools)
- [Obsidian settings the vault assumes](#obsidian-settings-the-vault-assumes)

## Where templates come from

Read the template from `08-System/Templates/<name>.md` in the vault every time.
The copy under this skill's `templates/` folder is only the seed the vault init
script uses. The user may edit a template in Obsidian, and a command, the app
and Obsidian must then all produce the edited shape.

## Placeholder subset

Obsidian's core Templates plugin supports `{{title}}`, `{{date}}` (default
`YYYY-MM-DD`), `{{time}}` (default `HH:mm`), and `{{date:FORMAT}}` and
`{{time:FORMAT}}` with Moment.js tokens.

The seed templates use only `{{title}}`, `{{date:YYYY-MM-DD}}` and
`{{date:YYYYMMDDHHmmss}}`.

Implement exactly `{{title}}`, `{{date}}`, `{{time}}`, `{{date:F}}` and
`{{time:F}}`, where `F` contains only the tokens `YYYY`, `MM`, `DD`, `HH`, `mm`,
`ss` and literal non-letter characters. Any other token is a template error:
stop and tell the user which token and which template.

`{{title}}` is the note's title, which is its file name stem. For a daily note
that is its date.

Within one operation that creates several notes, each `id` advances one second
per note (C20).

## The six templates

| Template | Type | Frontmatter keys, in order | Body headings |
|---|---|---|---|
| `task.md` | `task` | `type`, `id`, `status`, `priority`, `project`, `created`, `due`, `tags` | `## Description`, `## Notes`, `## Links` |
| `project.md` | `project` | `type`, `id`, `status`, `created`, `tags` | `## Goal`, `## Scope`, `## Notes`, `## Links` |
| `daily.md` | `daily` | `type`, `id`, `created`, `tags` | `# Standup - {{title}}`, then `## Done`, `## Today`, `## Blockers`, `## Decisions / Updates`, `## Follow-ups`, `## Related Tasks / Projects` |
| `decision.md` | `decision` | `type`, `id`, `status`, `project`, `created`, `decided`, `tags` | `## Context`, `## Options considered`, `## Decision`, `## Consequences`, `## Links` |
| `lesson.md` | `lesson` | `type`, `id`, `status`, `project`, `created`, `tags` | `## Context`, `## What happened`, `## Lesson`, `## Apply next time`, `## Links` |
| `capture.md` | `capture` | `type`, `id`, `status`, `created`, `tags` | none; the captured text is the body |

A key with no value is YAML null. `tags: []` is an empty list. The templates
keep `project:` empty; a tool writes it as a wikilink when a project is given.
The `daily` template has no blank line after its frontmatter.

## Keys set by tools

Set these only when needed:

- `project` as a wikilink (see [links.md](links.md#project-values-and-slugs)).
- `blocked_by` on a task.
- `decided` on a decision, when its status becomes `accepted`.
- `classification` and `triaged_to` on a capture.

When a task is marked `done` with evidence, append the evidence under
`## Notes`.

## Obsidian settings the vault assumes

The user sets these in Obsidian and they are committed with `.obsidian/`.

| Setting | Value |
|---|---|
| Templates folder | `08-System/Templates` |
| Daily notes folder, format, template | `01-Daily`, `YYYY/YYYY-MM-DD`, `08-System/Templates/daily` |
| Use `[[Wikilinks]]` | On |
| New link format | Shortest path when possible |
| Automatically update internal links | On |
| Default location for new notes | `00-Inbox` |
| Property types, if Obsidian infers otherwise | `id`: text; `created`, `due`, `decided`: date |
| Obsidian Sync | Off (C14) |
