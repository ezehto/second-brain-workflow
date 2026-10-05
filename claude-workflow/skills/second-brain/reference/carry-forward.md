# Carry-forward and headings

Audience: a Claude Code session creating or filling a daily note, or appending
text under a heading. Source: plan sections 2.2 and 2.4.

## Contents

- [When carry-forward runs](#when-carry-forward-runs)
- [Untouched](#untouched)
- [What goes in each section](#what-goes-in-each-section)
- [Rules](#rules)
- [Locating a heading](#locating-a-heading)

## When carry-forward runs

"Today" is the `today` value from the `env` call described in
[../SKILL.md](../SKILL.md#vault-path-and-todays-date), read once per operation.
A `refused:` line means report it and stop. Take the date from nowhere else. The
daily note is `01-Daily/YYYY/YYYY-MM-DD.md`.

Carry-forward fills today's note in one of two
cases:

1. **Today's note does not exist.** Create it from the vault's `daily` template
   and fill it.
2. **Today's note exists and is untouched.** Fill it in place. Obsidian's Daily
   notes plugin may have created it first. Immediately before writing, re-read the
   file and confirm it is byte-identical to the content you judged untouched.
   If it differs, treat the note as touched and leave it unchanged.

If the note is touched, return it unchanged. Do not regenerate or merge.

Read task notes from disk directly, so a task marked done in Obsidian seconds
ago is not carried.

If the user is typing in that note in Obsidian at the same moment, Obsidian's
autosave can overwrite the fill. This risk is accepted; the vault's git history
makes any loss recoverable.

## Untouched

Compare against the **current** vault template (`08-System/Templates/daily.md`),
because the user may edit it.

1. Render the template's body (everything after its frontmatter) for the note's
   date.
2. Compare it with the note's body (everything after the note's frontmatter),
   ignoring all whitespace differences.
3. Equal, and the note's frontmatter parses with `type: daily`: untouched.
   Anything else: touched.

Frontmatter is excluded from the comparison because `id` and `created` depend on
the moment of creation and Obsidian may reformat it.

Insert carry-forward items under whichever of the six standup headings exist in
the note. If a customised template dropped one, add it using rule 6 under
[Locating a heading](#locating-a-heading).

## What goes in each section

Inputs: the task notes, and the **previous daily note** `P`, which is the daily
note with the latest date strictly before today. Weekends and gaps are handled
by that rule.

The definition of a valid due date is in [conventions.md](conventions.md#dates).
An invalid `due` counts as no due date.

| Section | Content |
|---|---|
| `## Done` | Empty. Nothing is assumed complete. |
| `## Today` | 1. Task items: `- [ ] [[Task]]` for every task with status `in-progress`, then `review`, then `planned` with a valid `due` on or before today. Within each status: `due` ascending (no valid due last), then title, then path. 2. Then free-text items: every unchecked item from `P`'s `## Today` section that contains no wikilink to a task note, copied verbatim, in the order they appear in `P`. |
| `## Blockers` | `- [[Task]]` for every task with status `blocked`, followed by ` (blocked by: <value>)` when `blocked_by` is set. Ordered like the task items in Today: `due` ascending (no valid due last), then title, then path. |
| `## Decisions / Updates` | Empty. |
| `## Follow-ups` | Every unchecked item from `P`'s `## Follow-ups` section, copied verbatim in the order they appear in `P`, including items that link a task. |
| `## Related Tasks / Projects` | `- [[Project]]` for each distinct resolved project of the task items placed under Today and Blockers, sorted by project title, then path. Resolve each `project` as in [links.md](links.md#resolving-a-link-or-project-value). Projects of free-text items are not considered. Unknown or duplicate project slugs are skipped. |

## Rules

- **Task status is authoritative for task links in Today. Checkboxes are
  authoritative for free text.** The task-link rule applies to `## Today` only.
  An unchecked item in `P`'s Today section that contains a wikilink resolving
  (as in [links.md](links.md#resolving-a-link-or-project-value), including
  ambiguous) to a note with `type: task` is dropped, because the task's current
  status already decides whether it is carried. An unresolved link does not
  count: such an item is free text. A stale checkbox must not resurrect a task
  closed in Obsidian.
- **Follow-ups are always copied** when unchecked, even if they link a task. A
  follow-up is a separate action about the task and exists nowhere else in
  today's note. Dropping it would assume completion.
- **Duplicates are removed within a section only**, keeping the first
  occurrence. The key is the task's path for task items. For free-text items it
  is the text after `- [ ] ` with whitespace runs collapsed and both ends
  trimmed, and it is case-sensitive. Nothing is de-duplicated across sections. A
  task cannot appear in two sections, because its status puts it in exactly one.
- **Unchecked** is a line matching `- [ ] `, also `* [ ] ` and `+ [ ] `, at any
  indentation (the indentation is kept). `- [x]` and `- [X]` are checked and
  never carried. Any other marker, such as `- [/]` or `- [-]`, counts as
  checked. Obsidian treats only a space as unchecked.
- Tasks with status `inbox`, `done` or `cancelled` are not carried. Nor are
  `planned` tasks with no valid due date or a future one. A `planned` task whose
  `due` is invalid is **not** carried: carrying on a guessed date would invent a
  deadline.
- Links follow [links.md](links.md#emitted-links): folder-qualified when the
  stem is not unique on disk.

## Locating a heading

Use this to append text under a section. The rules need no Markdown parser.

1. Skip the frontmatter block and every fenced code block (code regions, see
   [links.md](links.md#code-regions)). Only ATX headings count: `#` to `######` followed by a space. Setext
   headings are not recognised.
2. The target is a level and a text, for example `## Today`. A heading matches
   when its level is equal and its text, with surrounding whitespace and
   trailing `#` characters removed, is equal ignoring case (Unicode casefold).
3. If several headings match, use the **first**.
4. The section ends just before the next heading of the same or a higher level
   (fewer or equal `#`), or at end of file.
5. Insert after the last non-blank line of the section. Keep exactly one blank
   line before the next heading. An empty section receives the text after one
   blank line below the heading.
6. If no heading matches, append the heading at the end of the file at the
   requested level, then the text. A renamed heading never loses appended text.
7. Preserve the file's existing line endings and BOM. The line ending is that
   of the file's first line break (`\r\n` means CRLF). A file with no line break
   uses LF.
8. **End of file.** When the insertion point is the end of the file (the target
   section is last, or rule 6 applies): trailing blank lines at the end of the
   file are removed. If the last remaining line has no line ending, one is
   added. For rule 6, exactly one blank line is written before the new heading.
   Then the new text is written, and the file ends with exactly one line ending.
   Nothing earlier in the file changes. This is the one end state that code and a
   Claude session produce identically.
