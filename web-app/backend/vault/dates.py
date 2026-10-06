"""The date rule of plan section 2.10, applied to a stored frontmatter value.

The parser reads dates from the loaded YAML; the index keeps only their text (`frontmatter`
is JSON), so a value that has no column (`decided`) is re-judged here from that text with the
parser's own patterns.
"""

from datetime import date, datetime

from ruamel.yaml.util import create_timestamp, timestamp_regexp

from vault.parser import _ISO_DATE_RE


def frontmatter_date(value) -> date | None:
    """The date of a stored frontmatter value, or None when it is not a valid date.

    Accepts exactly what the parser accepts: `YYYY-MM-DD`, or YAML timestamp text
    (`2026-02-20T10:00:00Z`, `2026-02-20 10:00:00`), whose date part is returned as written
    with no timezone conversion. Anything else is None: a non-string, `2026-02-20x`,
    `2026-W07-5`, `2026-02-20 later`, or an impossible day such as `2026-02-30`.

    Known residue: the stored text cannot tell a quoted string from a bare YAML timestamp,
    so a quoted `"2026-02-20 10:00:00"` is judged valid here although `parse_note` treats a
    quoted value as a string and rejects it. The reverse never happens.
    """
    if not isinstance(value, str):
        return None
    try:
        if _ISO_DATE_RE.fullmatch(value):
            return date.fromisoformat(value)
        matched = timestamp_regexp.match(value)
        if matched is None:
            return None
        result = create_timestamp(**matched.groupdict())
    except ValueError:
        return None
    return result.date() if isinstance(result, datetime) else result
