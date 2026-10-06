"""File-name sanitising (plan section 2.5, rules 1 to 8). Pure functions, no I/O.

This is the leaf module of the writer: it also defines `WriterError`, the base class of every
error the writer raises (see the map in `vault.writer`).
"""

import unicodedata

from vault import conventions

MAX_STEM_LENGTH = 100  # rule 7, in code points
MAX_STEM_BYTES = 233  # rule 7, UTF-8; leaves room for `.md` and the writer's temp-file suffix


# Format (Cf) characters rule 2 keeps: ZWNJ and ZWJ (U+200C, U+200D); the tag characters
# U+E0020 to U+E007F are kept too (flag sequences).
KEPT_FORMAT_CHARACTERS = frozenset("\u200c\u200d")


class WriterError(Exception):
    """Base of every error the writer raises."""


class SanitizeError(ValueError, WriterError):
    """Nothing usable remains of a title after sanitising."""


def utf16_length(text: str) -> int:
    """Length in UTF-16 code units: how Windows measures a path (2.5 rule 7)."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def is_reserved_name(name: str) -> bool:
    """True for a Windows device name: the part before the first dot, trailing spaces removed,
    case-insensitive (`con`, `NUL.txt`, `COM1 .md`)."""
    device = name.partition(".")[0].rstrip(" ").upper()
    return (
        device in conventions.RESERVED_DEVICE_NAMES
        or device in conventions.SUPERSCRIPT_DEVICE_NAMES
    )


def sanitize_stem(title: str, *, fallback: str | None = None) -> str:
    """Turn a title into a file name stem, applying every rule of 2.5 in order.

    An empty result returns `fallback` when one is given (rule 8 passes
    `Untitled YYYY-MM-DD HHmmss`), otherwise raises `SanitizeError`.
    """
    text = unicodedata.normalize("NFC", title)  # 1
    # 2: control (Cc), surrogate (Cs) and format (Cf) characters go, except the joiners and tag
    # characters that emoji sequences and Persian need; line and paragraph separators (Zl, Zp)
    # become spaces, which rule 4 collapses.
    kept = []
    for char in text:
        category = unicodedata.category(char)
        if category in ("Zl", "Zp"):
            kept.append(" ")
        elif category == "Cf":
            if char in KEPT_FORMAT_CHARACTERS or "\U000e0020" <= char <= "\U000e007f":
                kept.append(char)
        elif category not in ("Cc", "Cs") and char not in conventions.CONTROL_CHARACTERS:
            kept.append(char)
    text = "".join(kept)
    replaced = (
        conventions.WINDOWS_ILLEGAL_CHARACTERS
        | conventions.LINK_BREAKING_CHARACTERS
        | conventions.SHELL_EXPANDED_CHARACTERS
    )
    text = "".join(" " if char in replaced else char for char in text)  # 3
    text = " ".join(text.split())  # 4
    text = text.lstrip(". ").rstrip(
        ". "
    )  # 5: a leading dot hides the file, Windows strips trailing ones
    if is_reserved_name(text):  # 6: `note` goes after the device name, before any extension
        base, dot, rest = text.partition(".")
        text = f"{base.rstrip(' ')} note{dot}{rest}"
    text = text[:MAX_STEM_LENGTH]  # 7: str slices code points, never half a pair
    while len(text.encode("utf-8")) > MAX_STEM_BYTES:
        text = text[:-1]
    text = text.rstrip(". ")
    if text:
        return text
    if fallback is not None:  # 8
        return fallback
    raise SanitizeError(f"nothing usable remains of the title {title!r}")
