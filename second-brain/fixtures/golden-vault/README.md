# Golden sample vault

The shared fixture for Phase 1 (task P1-06). The parser, the conformance
checker, the nine commands, the indexer, the writer and the API are all tested
against this one vault and the expectations under `expected/`, so they cannot
drift apart. Every expected value was derived by hand from the written rules in
`docs/plan/phase-1-foundation.md`, not by running a parser.

Audience: whoever writes or reviews a component that reads or writes the vault.

## Contents

- [Reference date and test clock](#reference-date-and-test-clock)
- [Layout](#layout)
- [Expected index format](#expected-index-format)
- [Expected checker result](#expected-checker-result)
- [Manifest](#manifest)
- [Non-obvious expected values](#non-obvious-expected-values)
- [Carry-forward scenarios](#carry-forward-scenarios)
- [Synthetic files](#synthetic-files)
- [Points the plan now decides](#points-the-plan-now-decides)
- [Notes for the parser task](#notes-for-the-parser-task)
- [Byte-exact files](#byte-exact-files)

## Reference date and test clock

Reference date: **2026-10-09** (a Friday). Timezone: Asia/Manila.

Every relative case is defined against this date, never against the day a test
runs: "past", "today" and "future" `due` values, the carry-forward scenario
date, and the missing days between daily notes. Tests pin it with the test
clock of plan section 2.12: `SECOND_BRAIN_TEST_MODE=1` and
`SECOND_BRAIN_TODAY=2026-10-09`, together with `SECOND_BRAIN_VAULT` pointing at
a copy of `vault/`.

The test clock pins the **date only**. The time of day comes from the real
clock, so a note written in test mode has `created: 2026-10-09` and an `id` that
matches `^20261009[0-9]{6}$`; no expectation here uses an exact `id` for a
note written during a test.

Daily notes exist for 2026-10-05 and 2026-10-07. There is none for 2026-10-06
(the gap day between them) or for 2026-10-08, so the previous daily note for
the reference date is 2026-10-07, which is not yesterday.

## Layout

| Path | Holds |
|---|---|
| `vault/` | The sample vault: 61 indexed notes, the six templates and the ignored paths. |
| `expected/index.json` | The expected parse result per indexed vault-relative path. |
| `expected/carry-forward/new-note/` | No note for the date: `scenario.json`, `expected-body.md`. |
| `expected/carry-forward/untouched-note/` | An untouched note: `scenario.json`, `input.md`, `expected.md`. |
| `expected/carry-forward/touched-note/` | A touched note that must stay unchanged: `scenario.json`, `input.md`. |

`second-brain/tests/test_fixture.py` checks this README's manifest against the files
and against `expected/index.json`.

## Expected index format

`expected/index.json` has `reference_date`, `timezone` and `notes`. `notes` maps
each indexed vault-relative path to these fields:

| Field | Meaning | Rule |
|---|---|---|
| `type` | `note` without usable frontmatter or `type`; otherwise the `type` string trimmed and lower-cased, unknown values kept | 2.10 |
| `title` | The file name stem | 2.9 |
| `status`, `priority` | Raw frontmatter value, or `null` | 2.3, 2.9 |
| `project` | The slug derived from `project`, or `null` | 2.1 |
| `due`, `created` | `YYYY-MM-DD`, or `null` when absent or invalid | 2.10 |
| `note_id` | Frontmatter `id` as a string, or `null` | 2.9 |
| `tags` | The note's tag set, sorted | 2.10 |
| `links` | The note's link set (one entry per distinct target), sorted | 2.8 |
| `parse_error` | Whether a parse error is set | 2.9 |

A path that is absent from `notes` must not be indexed. Paths with
`Indexed` = `no` in the manifest are those.

## Expected checker result

The `Checker` column of the manifest lists the distinct codes of plan section
2.11 that the conformance checker must report for each indexed note; `none`
means no line for that note. Ignored paths and the files under `expected/` are
`not checked`. No vault-level code applies: all six templates are present, so
F6 is not reported.

Checker exit code for the whole vault: **1** (failures F1, F2, F3, F4, F5, F7
and F8 are present). F1 is reported for the four malformed notes only.

Notes without frontmatter, with empty frontmatter, with no usable string
`type`, or with a type outside the six known ones are checked for failures F1
and F5 only; the only warning that can apply to them is W4, and only for a
string `type` outside the six (2.11). So `Meeting with unknown type.md` gets W4
and `Type that is not a string.md` (`type: 42`, indexed as `note`) gets none.

Checker output format (2.11), for the checker task (P1-08): one line per note
and code, `<code> <vault-relative path>: <message>`, sorted by path then code.
Several problems with the same code in one note are one line whose message
lists them, so `Tag rules.md` gives a single `W6` line naming both dropped
items (`2024` and `two words`). The `Checker` column therefore lists each code
once per note, and the expected output on this vault is exactly one line per
code listed in that column. The message text is not fixed; tests compare the
code and the path.

## Manifest

Every file in `vault/` and `expected/`, mapped to the cases it covers, the
checker codes it must produce and the rule it exercises. Rule numbers are
sections of `docs/plan/phase-1-foundation.md`. The case ids in `Covers` are
the ones `test_fixture.py` requires, plus extra ids for cases this fixture adds.

| Path | Indexed | Covers | Checker | Rule and expected value |
|---|---|---|---|---|
| `vault/00-Inbox/2026-10-06 1402 Plan the lantern rollout before the festival.md` | yes | `valid-capture`, `capture-triaged`, `capture-name` | none | 2.3, 3.2: `triaged`; `triaged_to` gives link `plan lantern rollout`. 2.5 rule 9: the text has seven words, all in the name. |
| `vault/00-Inbox/2026-10-07 1730 Tides seem higher this week.md` | yes | `capture-dismissed`, `capture-name` | none | 2.3: `dismissed`. 2.5 rules 9 and 5: the trailing `.` of `week.` is stripped. |
| `vault/00-Inbox/2026-10-08 0915 Buy a spare hinge for the gate.md` | yes | `valid-capture`, `capture-inbox`, `capture-name` | none | 2.3: `inbox`. One of three inbox captures for P1-12. |
| `vault/00-Inbox/2026-10-08 1240 Maybe the lanterns could change colour at dusk.md` | yes | `capture-inbox`, `capture-name` | none | 2.5 rule 9: the first 8 words of the text, unchanged. |
| `vault/00-Inbox/2026-10-08 1605 Why do the garden lights flicker after rain.md` | yes | `capture-inbox`, `capture-name` | none | 2.5 rules 9, 3 and 4: the 8th word is `rain?`; `?` becomes a space and is trimmed. |
| `vault/00-Inbox/Empty note.md` | yes | `empty-file` | none | 2.9: zero bytes, so no frontmatter: `type: note`, every field `null`, no parse error. |
| `vault/00-Inbox/Empty frontmatter block.md` | yes | `empty-frontmatter` | none | 2.9: `---` directly followed by `---` is valid frontmatter with no keys, not malformed: no parse error, `type: note`, every field `null`; the body starts after the closing line. 2.11: checked for F1 and F5 only. |
| `vault/00-Inbox/Frontmatter that is a list.md` | yes | `non-mapping-frontmatter` | `F1` | 2.9: a non-mapping document: parse error, `type: note`. |
| `vault/00-Inbox/Frontmatter without type.md` | yes | `frontmatter-without-type`, `tags-frontmatter`, `tags-comma-string` | none | 2.10: no `type` key gives `note`; `tags: garden,outdoor` gives `garden`, `outdoor`. Type `note` is checked for F1 and F5 only. |
| `vault/00-Inbox/Loose thoughts without frontmatter.md` | yes | `no-frontmatter`, `tags-inline` | none | 2.10: `#Idea` and `#garden/lighting` give `idea` and `garden/lighting`; link `quiet garden`. |
| `vault/00-Inbox/Meeting with unknown type.md` | yes | `unknown-type` | `W4` | 2.10: `type: Meeting` is indexed as `meeting`, not `note`; `status: scheduled` is stored as-is, no vocabulary (2.3). |
| `vault/00-Inbox/Type that is not a string.md` | yes | `non-string-type` | none | 2.10: `type: 42` is not a string, so `note`. Checked for F1 and F5 only. |
| `vault/00-Inbox/Task in the wrong folder.md` | yes | `wrong-folder` | `F4` | 2.11: a `task` outside `02-Work/Tasks/`. `done`, so never carried. |
| `vault/00-Inbox/Drafts/Draft ignored by directory rule.md` | no | `ignored-sbignore`, `ignored-sbignore-directory` | not checked | 2.9: `00-Inbox/Drafts/` is in `.sbignore`. An inbox capture `/triage` must not see. |
| `vault/01-Daily/2026/2026-10-05.md` | yes | `valid-daily`, `daily-gap` | none | Older than the previous note, so `Call the hardware store` is never carried (2.2). |
| `vault/01-Daily/2026/2026-10-07.md` | yes | `valid-daily`, `daily-gap`, `tags-inline`, `link-ambiguous`, `cf-today-links-task`, `cf-today-unresolved`, `cf-followup-links-task`, `cf-duplicate-in-section`, `cf-same-text-two-sections`, `cf-checkbox-markers`, `cf-star-and-indent` | none | The previous daily note `P` (2.2). See [Carry-forward scenarios](#carry-forward-scenarios). |
| `vault/02-Work/Projects/Harbor Lights.md` | yes | `valid-project`, `project-note`, `space-name` | none | 2.1: slug `harbor-lights`. |
| `vault/02-Work/Projects/Quiet Garden.md` | yes | `project-note` | none | 2.1: slug `quiet-garden`; `paused` still resolves. |
| `vault/02-Work/Projects/Lantern Festival.md` | yes | `project-note`, `same-name-different-folders` | none | 2.1: slug `lantern-festival`. Its stem is shared with a decision. |
| `vault/02-Work/Projects/Night Owl.md` | yes | `duplicate-project-slug` | none | 2.1: slug `night-owl`, shared with `Night-Owl`, so neither resolves. |
| `vault/02-Work/Projects/Night-Owl.md` | yes | `duplicate-project-slug` | none | As above; `archived`. |
| `vault/02-Work/Projects/lantern-diagram.png` | no | `ignored-non-md` | not checked | 2.9: not a `.md` file. Target of the attachment link. |
| `vault/02-Work/Tasks/Draft onboarding guide.md` | yes | `valid-task`, `task-inbox`, `due-past`, `project-wikilink` | none | 2.2: `inbox` is never carried, even overdue. |
| `vault/02-Work/Tasks/Plan lantern rollout.md` | yes | `task-planned`, `due-past`, `project-slug` | none | 2.1: plain slug `harbor-lights`. 2.2: carried. |
| `vault/02-Work/Tasks/Inspect the pier lamps.md` | yes | `task-planned`, `due-today`, `timestamp-due` | none | 2.10: `due: 2026-10-09T23:30:00-02:00` is a timestamp; its date as written, with no timezone conversion, is `2026-10-09`. 2.2: carried. |
| `vault/02-Work/Tasks/Order replacement bulbs.md` | yes | `task-planned`, `due-today`, `project-duplicate-slug` | `W5` | 2.1: `night-owl` matches two project notes and resolves to neither. 2.2: carried; adds no Related project. |
| `vault/02-Work/Tasks/Paint the gate.md` | yes | `task-planned`, `due-future` | none | 2.2: future `due`, not carried. |
| `vault/02-Work/Tasks/Sort the seed packets.md` | yes | `task-planned`, `due-none` | none | 2.2: no `due`, not carried. |
| `vault/02-Work/Tasks/Label the storage boxes.md` | yes | `task-planned`, `invalid-date`, `invalid-due-planned` | `F7` | 2.10: `due: next week` is invalid: `null`. 2.2: a planned task with no valid due is not carried. |
| `vault/02-Work/Tasks/Check the ladder rungs.md` | yes | `task-planned`, `invalid-due-planned` | `F7` | 2.9, 2.10: `due: 2026-13-01` is an invalid value, not malformed frontmatter: no parse error, other keys kept, `due` `null`; not carried. See [Notes for the parser task](#notes-for-the-parser-task). |
| `vault/02-Work/Tasks/Release checklist.md` | yes | `task-in-progress`, `due-past`, `same-name-different-folders` | none | Same stem as a lesson. 2.5: carried as `[[02-Work/Tasks/Release checklist]]`. |
| `vault/02-Work/Tasks/Wire the dock lights.md` | yes | `task-in-progress`, `due-future`, `project-alias-wikilink` | none | 2.1: `"[[Harbor Lights\|the harbor]]"` gives `harbor-lights`. The `.trash/` copy does not make the stem duplicate. |
| `vault/02-Work/Tasks/Calibrate light sensor.md` | yes | `task-in-progress`, `due-none`, `project-unknown-slug` | `W5` | 2.1: `lighthouse-tour` matches no project note. 2.2: last among in-progress. |
| `vault/02-Work/Tasks/Review path layout.md` | yes | `task-review`, `due-today`, `project-folder-wikilink` | none | 2.1: folder prefix dropped: `harbor-lights`. 2.8: the link keeps the folder: `02-work/projects/harbor lights`. |
| `vault/02-Work/Tasks/Fix gate latch.md` | yes | `task-blocked`, `due-past`, `blocked-by`, `blocked-different-due`, `related-from-blockers` | none | 2.2: first in Blockers (due 10-08). Its project `Quiet Garden` is the only reason that project is under Related. |
| `vault/02-Work/Tasks/Replace fence post.md` | yes | `task-blocked`, `due-future`, `blocked-different-due` | none | 2.2: second in Blockers (due 10-15); no `blocked by` suffix; no project. |
| `vault/02-Work/Tasks/Test solar panel.md` | yes | `task-done`, `due-today` | none | 2.2: `done` is never carried. |
| `vault/02-Work/Tasks/Survey the old shed.md` | yes | `task-cancelled`, `due-future` | none | 2.2: `cancelled` is never carried. |
| `vault/02-Work/Tasks/Tidy the toolshed.md` | yes | `unknown-status`, `due-past` | `F3` | 2.3: `someday` is stored as-is. 2.2: not a carried status. |
| `vault/02-Work/Tasks/Task without status.md` | yes | `missing-required-key` | `F2` | 2.11: a `task` must have `status`. Not carried. |
| `vault/02-Work/Tasks/Task with invalid priority.md` | yes | `invalid-priority` | `F8` | 2.11: `priority: urgent`. `done`. |
| `vault/02-Work/Tasks/Task with unknown keys and comments.md` | yes | `unknown-keys-and-comments` | none | Design D: `estimate_hours`, `reviewer` kept. YAML comments are not values: status `planned`. |
| `vault/02-Work/Tasks/Obsidian formatted properties.md` | yes | `obsidian-properties`, `synthetic`, `tags-frontmatter` | none | **Synthetic.** Block lists, `id` quoted as text, `aliases`. `note_id` `20261004111500`; tags `garden`, `outdoor`. |
| `vault/02-Work/Tasks/Broken yaml task.md` | yes | `malformed-yaml` | `F1` | 2.9: unclosed `[`. Parse error; the body is the whole file, so the `[[Harbor Lights]]` in the broken block is a body link: `harbor lights`. |
| `vault/02-Work/Tasks/Unterminated frontmatter task.md` | yes | `unterminated-frontmatter` | `F1` | 2.9: no closing `---` or `...`. |
| `vault/02-Work/Tasks/Duplicate keys task.md` | yes | `duplicate-keys` | `F1` | 2.9: `status` twice; `note_id` `null` (frontmatter is `{}`). |
| `vault/02-Work/Tasks/Ignored by sbignore.md` | no | `ignored-sbignore` | not checked | 2.9: listed in `.sbignore` by path. An in-progress task that must not be carried. |
| `vault/02-Work/Tasks/Scratch pad.md` | no | `ignored-sbignore`, `sbignore-glob` | not checked | 2.9: matched by the glob `02-Work/Tasks/Scratch *.md`. An in-progress task that must not be carried. |
| `vault/02-Work/Tasks/.Paint the gate.sbw-tmp-3f9a1c0e` | no | `ignored-writer-temp` | not checked | 2.9: writer temp name. |
| `vault/05-Knowledge/Decisions/Use warm white bulbs.md` | yes | `valid-decision`, `duplicate-id` | `W2` | `id` 20261003150000, shared with its copy. |
| `vault/05-Knowledge/Decisions/Use warm white bulbs 1.md` | yes | `duplicate-id` | `W2` | A byte-identical copy, as Obsidian's "Make a copy" leaves it. |
| `vault/05-Knowledge/Decisions/Byte order mark decision.md` | yes | `bom`, `project-slug` | none | 2.9: frontmatter starts after the BOM: `decision`, `proposed`, slug `quiet-garden`. |
| `vault/05-Knowledge/Decisions/Frontmatter closed with dots.md` | yes | `dots-terminator` | none | 2.9: the block ends at a `...` line and parses. |
| `vault/05-Knowledge/Decisions/Lantern Festival.md` | yes | `same-name-different-folders` | none | Same stem as the project. Its folder-qualified `project` is not ambiguous (no W3): slug `lantern-festival`. |
| `vault/05-Knowledge/Lessons/Release checklist.md` | yes | `valid-lesson`, `same-name-different-folders` | none | Same stem as the task. |
| `vault/05-Knowledge/Lessons/Festival lighting lesson.md` | yes | `project-duplicate-stem` | `W3` | 2.11: bare `"[[Lantern Festival]]"` to a stem that is not unique on disk. Slug `lantern-festival` resolves to the one project note, so no W5. |
| `vault/05-Knowledge/Lessons/Café lights need weatherproof plugs.md` | yes | `non-ascii-name`, `space-name` | none | Name in NFC on disk. |
| `vault/05-Knowledge/Lessons/Windows line endings lesson.md` | yes | `crlf` | none | 2.9: CRLF frontmatter parses. |
| `vault/05-Knowledge/Lessons/Missing id lesson.md` | yes | `missing-id` | `W1` | No `id`; `note_id` `null`, no parse error. |
| `vault/05-Knowledge/Lessons/Lamp sizes #2.md` | yes | `unsafe-file-name` | `F5` | 2.11, 2.5 rule 3: `#` is in the sanitising set. |
| `vault/05-Knowledge/Lessons/Every link form.md` | yes | `link-plain`, `link-alias`, `link-escaped-pipe`, `link-heading`, `link-block`, `link-same-note`, `link-embed`, `link-folder`, `link-md-extension`, `link-attachment`, `link-folder-qualified-duplicate`, `link-ambiguous`, `link-unresolved`, `link-frontmatter-list`, `link-case-whitespace`, `link-nfd`, `link-alias-unused`, `link-markdown-not-indexed`, `tags-frontmatter` | none | 2.8, every form. See [Non-obvious expected values](#non-obvious-expected-values). |
| `vault/05-Knowledge/Lessons/Repeated links to one target.md` | yes | `repeated-link` | none | 2.8 link set: five spellings and an embed of Harbor Lights give one entry, `harbor lights`. |
| `vault/05-Knowledge/Lessons/Tag rules.md` | yes | `tags-in-links`, `tag-not-numeric`, `tag-nested`, `tag-trailing-slash`, `tag-mixed-case`, `tag-not-mid-word`, `frontmatter-tag-hash`, `frontmatter-tag-comma-spaces`, `frontmatter-tag-numeric`, `frontmatter-tag-whitespace`, `tags-inline` | `W6` | 2.10. See [Non-obvious expected values](#non-obvious-expected-values). |
| `vault/05-Knowledge/Lessons/Fake links and tags in code.md` | yes | `fake-links-and-tags-in-code`, `tags-inline` | none | 2.8, 2.10: code spans and fences are skipped. Only `harbor lights` and `realtag` count. |
| `vault/05-Knowledge/Lessons/No trailing newline lesson.md` | yes | `no-trailing-newline` | none | For the writer's 2.4 rule 8: the last line has no line ending. |
| `vault/05-Knowledge/Lessons/Trailing blank lines lesson.md` | yes | `trailing-blank-lines` | none | For 2.4 rule 8: the file ends with three blank lines. |
| `vault/08-System/Templates/capture.md` | no | `template-copy` | not checked | 2.9: ignored folder. Byte-identical to the seed. |
| `vault/08-System/Templates/daily.md` | no | `template-copy` | not checked | As above. The template the untouched check renders. |
| `vault/08-System/Templates/decision.md` | no | `template-copy` | not checked | As above. |
| `vault/08-System/Templates/lesson.md` | no | `template-copy` | not checked | As above. |
| `vault/08-System/Templates/project.md` | no | `template-copy` | not checked | As above. |
| `vault/08-System/Templates/task.md` | no | `template-copy` | not checked | As above; it says `type: task` and must not be indexed. |
| `vault/.obsidian/app.json` | no | `ignored-obsidian` | not checked | Hand-written stand-in for the 3.3 link settings. |
| `vault/.obsidian/daily-notes.json` | no | `ignored-obsidian` | not checked | Hand-written stand-in for the 3.3 Daily notes settings. |
| `vault/.obsidian/templates.json` | no | `ignored-obsidian` | not checked | Hand-written stand-in for the 3.3 Templates folder. |
| `vault/.obsidian/Note inside the obsidian folder.md` | no | `ignored-obsidian` | not checked | 2.9: a `.md` file under a dot segment. |
| `vault/.trash/Wire the dock lights.md` | no | `ignored-trash` | not checked | 2.9: an in-progress task with the stem of a live task. |
| `vault/.sbignore` | no | `ignored-dotfile`, `sbignore-list` | not checked | 2.9: a comment, a file path, a glob and a directory. |
| `vault/.gitattributes` | no | `ignored-dotfile` | not checked | 2.6: `* -text`; also keeps the CRLF and BOM bytes intact. |
| `expected/index.json` | no | `expected-index` | not checked | The expected parse result. |
| `expected/carry-forward/new-note/scenario.json` | no | `carry-forward-new-note` | not checked | 2.2, 2.12: date, test clock, frontmatter shape, items per section. |
| `expected/carry-forward/new-note/expected-body.md` | no | `carry-forward-new-note` | not checked | 2.2, 2.4: the body after the frontmatter. |
| `expected/carry-forward/untouched-note/scenario.json` | no | `carry-forward-untouched-note` | not checked | 2.2: as for new-note, plus input and expected files. |
| `expected/carry-forward/untouched-note/input.md` | no | `carry-forward-untouched-note`, `synthetic` | not checked | **Synthetic.** An untouched daily note as Obsidian's Daily notes plugin creates it. |
| `expected/carry-forward/untouched-note/expected.md` | no | `carry-forward-untouched-note` | not checked | 2.2, 2.4: the same note filled in place. |
| `expected/carry-forward/touched-note/scenario.json` | no | `carry-forward-touched-note` | not checked | 2.2: the note must be returned unchanged. |
| `expected/carry-forward/touched-note/input.md` | no | `carry-forward-touched-note` | not checked | A daily note for the date with one typed item under Today: touched. |

## Non-obvious expected values

Each value below follows from the rule named; none was produced by running code.

**Links in `Every link form.md`** (2.8). Expected link set, sorted:
`05-knowledge/lessons/release checklist`, `café lights need weatherproof plugs`,
`calibrate light sensor`, `fix gate latch`, `garden lamp task`, `harbor lights`,
`moonlight budget`, `order replacement bulbs`, `paint the gate`,
`plan lantern rollout`, `release checklist`, `review path layout`,
`unresolved from frontmatter`, `use warm white bulbs`, `wire the dock lights`.

- `project: "[[Harbor Lights]]"` is a frontmatter string, so it gives `harbor lights`.
- The `related` list holds `[[Plan lantern rollout#Description]]`
  (`plan lantern rollout`), `[[Order replacement bulbs#^step-one]]`
  (`order replacement bulbs`) and `[[#Context]]` (not stored).
- `[[Calibrate light sensor|the sensor task]]` and the table cell
  `[[Fix gate latch\|the latch]]` drop the display text.
- `![[Use warm white bulbs]]` is stored like a link; `[[Paint the gate.md]]` loses `.md`.
- `[[  REVIEW   path layout ]]` is trimmed, collapsed and casefolded.
- The `Café` link is written in NFD (`e` plus U+0301); NFC gives the file name's target.
- `[[lantern-diagram.png]]` and `![[wiring-plan.pdf]]` are attachments: not stored.
- `[the gate](Paint%20the%20gate.md)` is a Markdown link: not indexed.
- Resolution: `[[Release checklist]]` is **ambiguous** and resolves to
  `02-Work/Tasks/Release checklist.md`, the shorter path (2.8 rule 4).
  `[[05-Knowledge/Lessons/Release checklist]]` resolves to the lesson (rule 1).
  `moonlight budget`, `unresolved from frontmatter` and `garden lamp task` are
  **unresolved**; the last is an `aliases` value, and aliases are not used (rule 6).

**Tags in `Tag rules.md`** (2.10). Expected tag set: `alpha`, `beta`, `eng`,
`eng/backend`, `v2`, `y1984`.

- Frontmatter `tags: "Alpha, #beta, 2024, two words"` is a comma string: items
  are trimmed and one leading `#` is removed, giving `alpha` and `beta`.
  `2024` (numeric only) and `two words` (internal whitespace) are dropped, so
  the checker reports W6.
- `[[Plan lantern rollout#Description]]`, `[[#Context]]` and
  `![[Order replacement bulbs#^step-one]]` are wikilinks; text inside them never
  gives a tag.
- `#1984` and `#2026/10` contain only digits and `/`: not tags. `a#b` has no
  whitespace before `#`; `http://example.com/#frag` has `/` before `#`: not tags.
- `#y1984` and `#v2` are tags. `#eng/backend` stays whole. `#eng/` loses the
  trailing `/` and, with `#Eng` and `#eng`, gives one tag `eng`.

**Project slugs** (2.1). `"[[Harbor Lights]]"`, `"[[Harbor Lights|the harbor]]"`,
`"[[02-Work/Projects/Harbor Lights]]"` and `harbor-lights` all give
`harbor-lights`. `lighthouse-tour` is unknown (W5). `night-owl` matches two
project notes, so it resolves to neither (W5). `"[[Lantern Festival]]"` gives
`lantern-festival`, which resolves to the one project note of that slug, but its
stem is shared with a decision (W3).

**Types** (2.10). `Meeting` gives `meeting`; `42` (not a string), no `type`
key, no frontmatter and malformed frontmatter give `note`.

**Dates** (2.10). `next week` and `2026-13-01` give `null`. The timestamp
`2026-10-09T23:30:00-02:00` gives `2026-10-09`: the date as written, although
the same instant is 2026-10-10 in UTC and in Manila.

**Malformed notes** (2.9). Four: `Broken yaml task.md`, `Unterminated
frontmatter task.md`, `Duplicate keys task.md` and `Frontmatter that is a
list.md`. Parse error, `frontmatter = {}`, body is the whole file, `type:
note`, checker code F1 only. Only `Broken yaml task.md` has a link in its body.
`Empty frontmatter block.md` is not malformed (2.9).

## Carry-forward scenarios

All three scenarios run carry-forward for **2026-10-09** with the test clock
set. The previous daily note `P` is `01-Daily/2026/2026-10-07.md` (2.2: latest
date strictly before today; 2026-10-08 does not exist). The new-note and
untouched-note scenarios produce the same body.

- `new-note`: no note exists for the date. The created file is the vault's
  `daily` template rendered for the date and filled: it equals
  `---\ntype: daily\nid: <id>\ncreated: 2026-10-09\ntags: []\n---\n` followed by
  `expected-body.md`, where `<id>` matches `^20261009[0-9]{6}$` (2.12). Every
  other byte is fixed.
- `untouched-note`: `input.md` is placed at `01-Daily/2026/2026-10-09.md`. Its
  body differs from the rendered template only by one extra blank line after
  the frontmatter, so it is untouched (2.2). It is filled in place; frontmatter
  and that blank line are unchanged; the result equals `expected.md` byte for
  byte. A command must re-read the file and confirm it is byte-identical
  immediately before writing (2.2).
- `touched-note`: `input.md` has one typed item under Today, so it is touched;
  the file must be byte-identical to `input.md` afterwards.

How each item was derived (2.2):

| Section | Item | Why |
|---|---|---|
| Today | `[[02-Work/Tasks/Release checklist]]` | In-progress, due 10-07. Folder-qualified: the stem is also a lesson (2.5). |
| Today | `[[Wire the dock lights]]` | In-progress, due 10-12. The `.trash/` copy is ignored. |
| Today | `[[Calibrate light sensor]]` | In-progress, no due: last among in-progress. |
| Today | `[[Review path layout]]` | Review. |
| Today | `[[Plan lantern rollout]]` | Planned, due 10-06. |
| Today | `[[Inspect the pier lamps]]` | Planned, due 10-09 (timestamp); before `Order…` by title. |
| Today | `[[Order replacement bulbs]]` | Planned, due 10-09. |
| Today | `- [ ] Buy more zip ties` | Free text; the later `- [ ] Buy  more zip ties ` has the same key after collapsing whitespace and is dropped (first kept). |
| Today | `    - [ ] Get the black ones` | Indented unchecked item; indentation kept. |
| Today | `- [ ] Check the [[Harbor Lights]] budget` | Links a project, not a task: free text. |
| Today | `- [ ] Ask about [[Moonlight budget]]` | Unresolved link does not count: free text. |
| Today | `* [ ] Oil the hinges` | `*` bullet is unchecked; copied verbatim. |
| Today | `- [ ] Charge the drill` | Free text. Also in Follow-ups; nothing is de-duplicated across sections. |
| Today, dropped | `[[Wire the dock lights]]`, `Retest [[Test solar panel]] after rain` | Link a task. |
| Today, dropped | `Read [[Release checklist]] before Friday` | The link is ambiguous and resolves to the task (2.8 rule 4), so the item links a task (2.2 counts ambiguous links). |
| Today, dropped | `- [x] Sweep…`, `- [X] Wipe…`, `- [/] Sand…` | Checked; `[/]` counts as checked. |
| Today, not carried | Paint the gate, Sort the seed packets, Task with unknown keys, Obsidian formatted properties | Planned with a future or no due. |
| Today, not carried | Label the storage boxes, Check the ladder rungs | Planned with an invalid due: no valid due date. |
| Today, not carried | Draft onboarding guide, Test solar panel, Survey the old shed, Tidy the toolshed, Task without status, Task with invalid priority, Task in the wrong folder | Not in a carried status. |
| Today, not carried | `Ignored by sbignore.md`, `Scratch pad.md`, `.trash/Wire the dock lights.md`, malformed task notes | Ignored, or `type: note`. |
| Today, not carried | `Call the hardware store` | In the 2026-10-05 note, which is not P. |
| Blockers | `[[Fix gate latch]] (blocked by: Waiting for hinge delivery)` | Due 10-08. |
| Blockers | `[[Replace fence post]]` | Due 10-15; no `blocked_by`. |
| Follow-ups | `- [ ] Email the supplier about lamp sizes` | Unchecked. |
| Follow-ups | `- [ ] Follow up on [[Fix gate latch]] with the supplier` | Links a task, still copied: the task-link rule applies to Today only. |
| Follow-ups | `- [ ] Charge the drill` | Same text as a Today item, kept. |
| Follow-ups | `- [ ] Confirm the delivery window for #hardware` | Unchecked. `[x] Send the photos` is dropped. |
| Related | `[[Harbor Lights]]` | Projects of Release checklist, Wire, Review, Plan. |
| Related | `[[Quiet Garden]]` | Only from Fix gate latch, a Blockers item. `lighthouse-tour` and `night-owl` are skipped. |

Formatting follows 2.4: each block sits one blank line below its heading, with
exactly one blank line before the next heading; empty sections stay empty.
Related is the last section, so rule 8 applies: the file ends with exactly one
line ending.

## Synthetic files

Two files stand in for files Obsidian itself must produce. P1-05 will produce
the real ones; the orchestrator then replaces these and re-runs the P1-07
parser tests, the `/daily` and `/standup` scenarios of P1-13 and, once it
exists, the untouched-note tests of P1-23. If the real untouched note differs,
`expected.md` must be re-derived from it (the filled body stays the same when
the real note is untouched; the frontmatter bytes become the real ones), and
`touched-note/input.md` should be rebuilt on the same frontmatter.

- `vault/02-Work/Tasks/Obsidian formatted properties.md`: a note as Obsidian's
  property editor formats it.
- `expected/carry-forward/untouched-note/input.md`: a daily note as Obsidian's
  Daily notes plugin creates it from `08-System/Templates/daily`.

The three `.obsidian/*.json` files are also hand-written stand-ins; nothing
reads them except to prove they are ignored.

## Points the plan now decides

Each point the first version of this fixture kept away from, and the rule that
now decides it.

| Point | Decided by |
|---|---|
| Inline tags inside wikilinks, numeric tags, nested and trailing `/`, case | 2.10 Tags |
| Frontmatter tags as a comma string with spaces, a `#` prefix, invalid items | 2.10 Tags; W6 in 2.11 |
| Unknown and non-string `type` | 2.3, 2.10 Types |
| Invalid and timestamp dates; a planned task with an invalid `due` | 2.10 Dates; 2.2 Rules |
| Order of every carry-forward section | 2.2 section table |
| Duplicates within and across sections | 2.2 Rules ("within a section only") |
| Follow-ups that link a task | 2.2 Follow-ups row and Rules |
| Which tasks feed Related | 2.2 ("Today and Blockers") |
| Checkbox markers, `*` bullets, indentation | 2.2 Rules |
| End of file after appending | 2.4 rule 8 |
| Link multiplicity | 2.8 Link set |
| Today's date and `id` in tests | 2.12 Test clock and Time of day |
| Required keys and checker verdicts | 2.11 |
| Empty frontmatter block | 2.9 "Malformed frontmatter" row: valid, no keys |
| A value the YAML library cannot load as its implied type | 2.9 "Malformed frontmatter" row: an invalid value under 2.10 |
| W4 for unknown and non-string types; checks for notes without a known type | 2.11 opening |
| Checker lines per code | 2.11 Output |

No point this fixture exercises is left undetermined by the plan.

## Notes for the parser task

Behaviour of ruamel.yaml in round-trip mode, as found by the reviewer and
re-checked for the new cases. It is library behaviour, not a source of expected
values.

- The unclosed flow sequence in `Broken yaml task.md` raises `ParserError`.
- Duplicate keys raise `DuplicateKeyError`.
- A non-mapping document does not raise: a list or a scalar loads as itself.
  `parse_error` for those must come from an explicit "is a mapping" check.
- An empty block (`---` then `---`, or only comments or blank lines) loads as
  `None`. 2.9 makes it valid frontmatter with no keys, so `None` must be
  treated as an empty mapping, **not** as a non-mapping document: no
  `parse_error` (`Empty frontmatter block.md`).
- An unquoted `due: 2026-13-01` makes the whole load raise `ValueError`
  ("month must be in 1..12"), because the value matches the YAML timestamp
  pattern. 2.9 makes it an invalid value under 2.10, not malformed
  frontmatter: no `parse_error`, the other keys are kept, and `due` is `null`.
  For `Check the ladder rungs.md` that means `type: task`, `status: planned`,
  `priority: medium`, `created: 2026-10-05`, `note_id: 20261005081500`,
  `due: null`, and checker code F7. The error is a plain `ValueError`, not a
  `ruamel.yaml.YAMLError`: a parser that catches only `YAMLError` crashes, and
  one that treats every exception as malformed frontmatter gets this note
  wrong. `2026-02-30` behaves the same way. One way to handle it: load
  normally first and, only on `ValueError`, reload without resolving
  timestamps and apply the 2.10 date rule. The fallback must still treat a
  timestamp-shaped scalar as a YAML timestamp (date as written); otherwise
  `Inspect the pier lamps.md` would lose its valid `due`.
- `type: 42` loads as an `int`. 2.10 makes a non-string `type` unusable, so the
  note is indexed as `note` (`Type that is not a string.md`).
- `2026-10-09T23:30:00-02:00` loads as a `TimeStamp` that keeps the written
  wall-clock time and offset; take its date as written.
- A `...` terminator is handled by the frontmatter splitter (2.9), not by YAML.

## Byte-exact files

Editors and tools normalise these silently; `test_fixture.py` checks the bytes.

- `Windows line endings lesson.md`: CRLF on every line, no bare LF.
- `Byte order mark decision.md`: starts with `EF BB BF` then `---`.
- `Empty note.md`: zero bytes.
- `No trailing newline lesson.md`: the last byte is not a line ending.
- `Trailing blank lines lesson.md`: ends with three blank lines.
- `Every link form.md`: the `Café` link text is NFD; the file name is NFC.
- `2026-10-07.md`: `- [ ] Buy  more zip ties ` keeps its double space and trailing space.
- `08-System/Templates/*.md`: byte-identical to `second-brain/templates/`.

The repository's `.gitattributes` does not normalise line endings and
`vault/.gitattributes` sets `* -text`, so these bytes survive a commit.
