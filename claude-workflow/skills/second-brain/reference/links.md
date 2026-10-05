# Links and project values

Audience: a Claude Code session that writes a wikilink or a `project` value.
Source: plan sections 2.1, 2.5 and 2.8, decisions C19 and C22.

## Contents

- [Emitted links](#emitted-links)
- [Project values and slugs](#project-values-and-slugs)
- [Resolving a link or project value](#resolving-a-link-or-project-value)
- [Code regions](#code-regions)

## Emitted links

Whenever you write a wikilink (in `project`, `triaged_to`, carry-forward items
or a `## Links` section), first check whether the target's stem is unique on
disk among the vault's `.md` files that are not ignored, ignoring case.

- Unique: write `[[Name]]`.
- Not unique: write the vault-relative path without `.md`:
  `[[02-Work/Tasks/Name]]`.

Walk the directory once per operation and reuse the result for every link in
that operation. Read the filesystem, never an index.

## Project values and slugs

| Rule | Detail |
|---|---|
| What you write | `project: "[[<Project title>]]"`, or `project: "[[02-Work/Projects/<Project title>]]"` when the stem is not unique on disk (C19). The templates keep `project:` empty. |
| Forms a person may type | A wikilink with or without alias, or a plain slug such as `project: loadup`. |
| A project's slug | `slugify` of the file name stem of a note with `type: project`. There is no `slug` key. |
| Given by slug or title | A `project:` argument matches by `slugify(arg) == slugify(stem)` over `type: project` notes, read from disk. No match: do not create the note, list the known projects and ask. More than one match: ask. |
| Slug clash | Creating a project is refused if a project note with the same slug already exists in `02-Work/Projects`. Check the filesystem. |

`slugify(s)`: Unicode NFKD, drop combining marks, lower-case, replace every run
of characters outside `[a-z0-9]` with `-`, trim leading and trailing `-`.
`"LoadUp"` becomes `loadup`. `"Strato GIDA v2"` becomes `strato-gida-v2`.

A project that is renamed in Obsidian keeps its wikilink-valued `project` keys.
A hand-typed plain slug does not follow a rename.

## Resolving a link or project value

Apply these rules whenever you need to know which note a link or a `project`
value points at. Carry-forward needs them, and the commands and the app must
agree on the golden fixture.

**A project value to a slug** (the indexed value). If the value is a wikilink,
drop the brackets, any alias, any heading and any folder prefix, then
`slugify`. Otherwise `slugify` the value.

**A slug to a project note.** The project note whose slug equals that value.
Match by `slugify(arg) == slugify(stem)` over notes with `type: project`. If no
note matches, it is an unknown project slug: not an error, do not invent one.
If two project notes have the same slug, neither resolves.

**A wikilink target.** Normalise it: NFC, case-fold, trim, collapse internal
whitespace, strip `.md`, use `/` as separator. Drop the alias, heading and block
parts (`[[A|alias]]`, `[[A#Heading]]`, `[[A#^block]]`, `![[A]]` all give `a`).
An escaped pipe inside a table, `[[A\|alias]]`, also gives `a`.
`[[#Heading]]` links to the same note. Ignore wikilinks inside code regions
(see [Code regions](#code-regions)).

An **attachment** is a link whose final path segment ends in one of these
extensions, matched case-insensitively on the final path segment: `png`, `jpg`,
`jpeg`, `gif`, `bmp`, `svg`, `webp`, `avif`, `pdf`, `mp3`, `wav`, `m4a`, `ogg`,
`flac`, `3gp`, `mp4`, `webm`, `mov`, `mkv`, `ogv`, `canvas`, `base`. An
attachment such as `[[image.png]]` or `![[file.pdf]]` is not a note. Any other
dotted name is a note title, so `[[Notes on Node.js]]` and `[[Version 2.0]]` are
note links. Then:

1. A target containing `/` matches the note whose vault-relative path without
   `.md`, case-folded, equals the target or ends with `/<target>`.
2. A bare target matches every note whose case-folded stem equals it.
3. Exactly one match: resolved.
4. More than one match: ambiguous. Resolve to the match with the shortest
   vault-relative path. On equal length, take the lexicographically first path.
   Report it as ambiguous. This is the app's own rule and does not claim to copy
   how Obsidian chooses.
5. No match: unresolved. Show it as such. It is not an error.
6. Frontmatter `aliases` are not used for resolution.

Repeated links to the same normalised target count once, and a link plus an
embed of it count once. Links whose spellings normalise to the same target
(`[[A]]`, `[[a|x]]`, `[[A#H]]`) also count once.

Only wikilinks count. Markdown-style links (text in brackets, path in
parentheses) are not links for this purpose. Links the system writes are folder-qualified whenever a stem is
duplicated, so ambiguity can only come from hand-written links.

## Code regions

One definition serves links, tags and the heading search alike.

- A **fenced code block** opens on a line whose first non-blank characters are
  three or more backticks or tildes, at any indentation of spaces or tabs, so a
  fence inside a list item counts. It closes on a later line that starts, after
  any indentation, with at least as many of the same character and nothing else
  but whitespace. An unclosed fence runs to the end of the file. Blockquote
  markers (`>`) before an opening or closing fence are ignored, so a fence
  inside a quote or a callout counts. A backtick fence's opening line has no
  further backtick on it, so a line that only starts with an inline span is not
  a fence.
- **Inline code spans** are backtick runs matched by a run of equal length. They
  do not cross a blank line.
- Indented code blocks without a fence are not code regions.
