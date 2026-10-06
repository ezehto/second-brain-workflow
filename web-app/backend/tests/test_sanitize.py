"""Tests for vault.sanitize: every rule of plan section 2.5, in order."""

import pytest

from vault import conventions
from vault.sanitize import (
    MAX_STEM_BYTES,
    MAX_STEM_LENGTH,
    SanitizeError,
    is_reserved_name,
    sanitize_stem,
    utf16_length,
)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Plain title", "Plain title"),
        ("Café", "Café"),  # 1: NFC
        ("a\x00b\x1fc\x7fd", "abcd"),  # 2: control characters are removed, not spaced
        ("tab\there", "tabhere"),
        ('a\\b/c:d*e?f"g<h>i|j', "a b c d e f g h i j"),  # 3: Windows-illegal
        ("a#b^c[d]e", "a b c d e"),  # 3: link-breaking
        ("cost $5 `x`", "cost 5 x"),  # 3: shell-expanded
        ("  many   spaces   here  ", "many spaces here"),  # 4
        (".hidden", "hidden"),  # 5
        ("...", None),
        ("name. . ", "name"),
        (". .a", "a"),
        ("con", "con note"),  # 6, case-insensitive
        ("NUL", "NUL note"),
        ("Com3", "Com3 note"),
        ("lpt9", "lpt9 note"),
        ("console", "console"),
        ("CON.", "CON note"),  # 5 runs before 6
        ("", None),  # 8 without a fallback
        ("   ", None),
        ("///", None),
    ],
)
def test_rules(title, expected):
    if expected is None:
        with pytest.raises(SanitizeError):
            sanitize_stem(title)
    else:
        assert sanitize_stem(title) == expected


def test_truncates_to_100_code_points_and_trims_again():
    assert sanitize_stem("x" * 150) == "x" * MAX_STEM_LENGTH
    assert sanitize_stem("a" * 99 + " tail") == "a" * 99
    assert sanitize_stem("a" * 98 + "..b") == "a" * 98
    astral = "\U0001f600" * 150  # 4 UTF-8 bytes each: the byte cap bites first, never mid-character
    assert sanitize_stem(astral) == "\U0001f600" * (MAX_STEM_BYTES // 4)
    assert len(sanitize_stem("\u00e9" * 150).encode()) <= MAX_STEM_BYTES
    assert len(sanitize_stem("\u65e5" * 150)) == MAX_STEM_BYTES // 3


def test_fallback_replaces_an_empty_result_only():
    assert (
        sanitize_stem("///", fallback="Untitled 2026-10-06 120000") == "Untitled 2026-10-06 120000"
    )
    assert sanitize_stem("ok", fallback="Untitled") == "ok"


def test_every_character_of_every_set_is_gone():
    sets = (
        conventions.CONTROL_CHARACTERS
        | conventions.WINDOWS_ILLEGAL_CHARACTERS
        | conventions.LINK_BREAKING_CHARACTERS
        | conventions.SHELL_EXPANDED_CHARACTERS
    )
    result = sanitize_stem("a" + "".join(sorted(sets)) + "b")
    assert not set(result) & sets


def test_is_idempotent():
    for title in ("A: b/c", "con", "x" * 120, " .a. "):
        once = sanitize_stem(title)
        assert sanitize_stem(once) == once


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("a\u200bb", "ab"),  # Cf: zero-width space
        ("a\u00adb", "ab"),  # Cf: soft hyphen
        ("a\ud800b", "ab"),  # Cs: lone surrogate
        ("a\u202eb", "ab"),  # Cf: right-to-left override
        ("a\ufeffb", "ab"),  # Cf: BOM / zero-width no-break space
        ("a\u0085b", "ab"),  # Cc: next line
        ("a\u2028b", "a b"),  # Zl becomes a space
        ("a\u2029b", "a b"),  # Zp becomes a space
        ("CON.txt", "CON note.txt"),  # the part before the first dot is the device name
        ("nul.tar.gz", "nul note.tar.gz"),
        ("COM1.", "COM1 note"),
        ("com\u00b9", "com\u00b9 note"),
        ("LPT\u00b2.x", "LPT\u00b2 note.x"),
        ("COM\u00b3", "COM\u00b3 note"),
        ("conf", "conf"),
        ("CON.", "CON note"),
    ],
)
def test_format_characters_and_extended_device_names(title, expected):
    assert sanitize_stem(title) == expected


def test_is_reserved_name_uses_the_part_before_the_first_dot():
    assert is_reserved_name("CON.md")
    assert is_reserved_name("aux .md")
    assert is_reserved_name("LPT\u00b9")
    assert not is_reserved_name("console.md")
    assert not is_reserved_name("a.CON")


def test_utf16_length_counts_surrogate_pairs_twice():
    assert utf16_length("abc") == 3
    assert utf16_length("\U0001f600") == 2
    assert utf16_length("\u65e5") == 1


def test_joiners_and_tag_characters_survive():
    family = "\U0001f468\u200d\U0001f469\u200d\U0001f467"
    persian = "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645"  # a word with a ZWNJ
    scotland = "\U0001f3f4" + "".join(chr(0xE0000 + ord(c)) for c in "gbsct") + "\U000e007f"
    for title in (family, persian, scotland):
        assert sanitize_stem(title) == title
    assert sanitize_stem("a\u202eb\ufeffc") == "abc"  # RLO and BOM go
