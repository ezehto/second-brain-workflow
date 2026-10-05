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
2. Remove control characters (U+0000 to U+001F, U+007F).
3. Replace each of `\ / : * ? " < > |` (illegal on Windows) and `# ^ [ ]`
   (break Obsidian links) with a space.
4. Collapse runs of whitespace to one space. Trim both ends.
5. Strip leading dots (a leading dot hides the file and looks like a writer
   temp file). Strip trailing dots and spaces (Windows removes them).
6. If the stem, ignoring case, is a Windows reserved device name (`CON`, `PRN`,
   `AUX`, `NUL`, `COM1` to `COM9`, `LPT1` to `LPT9`), append ` note`.
7. Truncate the stem to 100 characters (code points; never split a surrogate
   pair), then trim again. The full vault-relative path must be at most
   200 characters. Reject a longer path and tell the user.
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
- Check the filesystem at write time. Never rely on an index; it can be a poll
  interval out of date.
