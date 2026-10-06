# Naming

Audience: a Claude Code session deriving a file name from a title. Source: plan
section 2.5. Daily notes are exempt: they are always `YYYY-MM-DD.md`.

## Contents

- [Sanitising a title](#sanitising-a-title)
- [Capture names](#capture-names)
- [Name clashes](#name-clashes)

## Sanitising a title

Apply in order, to the title that becomes the file name stem.

1. Normalise to Unicode NFC.
2. Remove every control (`Cc`), surrogate (`Cs`) and format (`Cf`) character
   (bidirectional controls, the BOM, the soft hyphen), except U+200C, U+200D and
   the tag characters U+E0020 to U+E007F, which are kept for emoji sequences,
   Persian and flags. Turn U+2028 and U+2029 into a space.
3. Replace each of `\ / : * ? " < > |` (illegal on Windows), `# ^ [ ]`
   (break Obsidian links) and `$` and the backtick (a shell expands them even in
   double quotes, so the lookup verbs cannot take them) with a space. The last
   two apply to names commands create: a hand-made note with `$` in its name is
   still valid.
4. Collapse runs of whitespace to one space. Trim both ends.
5. Strip leading dots (a leading dot hides the file and looks like a writer
   temp file). Strip trailing dots and spaces (Windows removes them).
6. If the part of the stem before its first dot (trailing spaces removed) is,
   ignoring case, a Windows reserved device name (`CON`, `PRN`, `AUX`, `NUL`,
   `COM1` to `COM9`, `LPT1` to `LPT9`, or `COM`/`LPT` plus `¹`, `²`, `³`),
   insert ` note` after that part: `NUL.report` becomes `NUL note.report`.
7. Truncate the stem to 100 characters (code points; never split a surrogate
   pair) and to 233 UTF-8 bytes, whichever is shorter, then trim again. The
   full vault-relative path must be at most 200 characters, counted in UTF-16
   code units (an emoji counts 2). Reject a longer path and tell the user.
8. An empty result becomes `Untitled YYYY-MM-DD HHmmss`.

Then add `.md`.

## Capture names

A capture is named `YYYY-MM-DD HHmm <first 8 words of the text>`. Sanitise the
result with the rules above.

## Name clashes

- **Same folder, ignoring case:** a create whose name equals an existing file's
  name, ignoring case, is rejected. Ask the user for a different title. For a
  capture only, retry once first with seconds added: `YYYY-MM-DD HHmmss <words>`.
- **Same name in a different folder:** allowed (C22). When you later link to
  such a note, use the folder-qualified form, see [links.md](links.md).
- Find clashes with the `stem` verb at write time (see
  [../SKILL.md](../SKILL.md#running-tools)). Any line, `note` or `ignored`, whose
  path is directly in the target folder, not in a subfolder, is a clash, because an ignored file of that name
  is still a file a write would overwrite. Lines in other folders are not
  clashes. Never rely on an index; it can be a poll interval out of date.
