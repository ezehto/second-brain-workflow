"""Tests for vault.parser: plan sections 2.9 and 2.10, against the golden fixture."""

import json
import random
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from vault import conventions
from vault.links import note_stem
from vault.parser import ParsedNote, parse_note, split_frontmatter

GOLDEN = Path(__file__).resolve().parents[3] / "second-brain" / "fixtures" / "golden-vault"
GOLDEN_VAULT = GOLDEN / "vault"
EXPECTED_NOTES = json.loads((GOLDEN / "expected" / "index.json").read_text(encoding="utf-8"))[
    "notes"
]


def golden(path: str) -> ParsedNote:
    return parse_note(path, (GOLDEN_VAULT / path).read_bytes())


def note(text: str, path: str = "02-Work/Tasks/Sample.md") -> ParsedNote:
    return parse_note(path, text.encode("utf-8"))


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


# --- The golden fixture, field by field -------------------------------------------------


def test_fixture_has_the_documented_number_of_notes():
    assert len(EXPECTED_NOTES) == 61


@pytest.mark.parametrize("path", sorted(EXPECTED_NOTES))
def test_golden_note_matches_expected_index(path):
    expected = EXPECTED_NOTES[path]
    parsed = golden(path)
    actual = {
        "type": parsed.type,
        "title": parsed.title,
        "status": parsed.status,
        "priority": parsed.priority,
        "project": parsed.project,
        "due": _iso(parsed.due),
        "created": _iso(parsed.created),
        "note_id": parsed.note_id,
        "tags": sorted(parsed.tags),
        "links": sorted(parsed.links),
        "parse_error": parsed.parse_error is not None,
    }
    assert actual == expected


# --- Malformed frontmatter (2.9) ---------------------------------------------------------

MALFORMED = [
    "02-Work/Tasks/Broken yaml task.md",
    "02-Work/Tasks/Unterminated frontmatter task.md",
    "02-Work/Tasks/Duplicate keys task.md",
    "00-Inbox/Frontmatter that is a list.md",
]


@pytest.mark.parametrize("path", MALFORMED)
def test_malformed_note_keeps_whole_file_as_body(path):
    raw = (GOLDEN_VAULT / path).read_bytes().decode("utf-8")
    parsed = golden(path)
    assert parsed.parse_error
    assert parsed.frontmatter == {}
    assert parsed.body == raw
    assert parsed.type == "note"


@pytest.mark.parametrize(
    "text",
    [
        "---\n- a\n- b\n---\n",
        "---\njust a scalar\n---\n",
        "---\n42\n---\n",
        "---\na: [unclosed\n---\n",
        "---\na: 1\na: 2\n---\n",
        "---\na: 1\n",
        "---",
        "---\nx: !!timestamp not-a-date\n---\n",
        "---\na: 1\n--- b\n---\n",
    ],
)
def test_malformed_cases_set_parse_error_and_never_raise(text):
    parsed = note(text)
    assert parsed.parse_error
    assert parsed.frontmatter == {}
    assert parsed.body == text
    assert parsed.type == "note"


@pytest.mark.parametrize("text", ["---\n---\n", "---\n# only a comment\n\n---\nBody", "---\n...\n"])
def test_empty_block_is_valid_frontmatter_with_no_keys(text):
    parsed = note(text)
    assert parsed.parse_error is None
    assert parsed.frontmatter == {}
    assert parsed.type == "note"


def test_empty_block_body_starts_after_closing_line():
    parsed = golden("00-Inbox/Empty frontmatter block.md")
    assert parsed.body == "\nThe frontmatter block has no lines.\n"


@pytest.mark.parametrize(
    "tag", ["!!python/object/apply:os.system", "!!python/name:os.system", "!!python/object:os.Foo"]
)
def test_python_object_tags_are_never_constructed(tag, tmp_path):
    marker = tmp_path / "pwned"
    parsed = note(f"---\nx: {tag} ['touch {marker}']\n---\n")
    assert not marker.exists()
    assert parsed.frontmatter == {"x": [f"touch {marker}"]}


def test_recursive_mapping_is_malformed_not_a_crash():
    parsed = note("---\n&r {a: *r}\n---\n")
    assert parsed.parse_error
    assert parsed.frontmatter == {}


def test_nested_recursive_alias_does_not_crash():
    parsed = note("---\na: &x [*x]\nb: ok\n---\n")
    assert parsed.frontmatter["b"] == "ok"


def test_value_cap_is_pinned():
    assert note("---\nbig: [" + ", ".join(["x"] * 9_000) + "]\n---\n").parse_error is None
    assert note("---\nbig: [" + ", ".join(["x"] * 20_000) + "]\n---\n").parse_error


def test_alias_expansion_bomb_is_malformed_not_a_hang():
    lines = ["a0: &a0 [x, x, x, x, x, x, x, x, x, x]"]
    for i in range(1, 9):
        refs = ", ".join([f"*a{i - 1}"] * 10)
        lines.append(f"a{i}: &a{i} [{refs}]")
    parsed = note("---\n" + "\n".join(lines) + "\n---\n")
    assert parsed.parse_error


# --- Frontmatter detection (2.9) ---------------------------------------------------------


def test_split_frontmatter_returns_yaml_text_and_body():
    assert split_frontmatter("---\na: 1\n---\nbody\n") == ("a: 1\n", "body\n", None)


@pytest.mark.parametrize(
    "text",
    ["", "body only\n", "\n---\na: 1\n---\n", " ---\na: 1\n---\n", "----\na: 1\n----\n"],
)
def test_text_without_opening_line_has_no_frontmatter(text):
    assert split_frontmatter(text) == (None, text, None)


def test_dots_close_the_block():
    parsed = golden("05-Knowledge/Decisions/Frontmatter closed with dots.md")
    assert parsed.parse_error is None
    assert parsed.frontmatter["type"] == "decision"
    assert parsed.body.startswith("\n## Context")


def test_closing_line_without_trailing_newline():
    parsed = note("---\ntype: task\n---")
    assert parsed.parse_error is None
    assert parsed.type == "task"
    assert parsed.body == ""


def test_bom_is_skipped_before_frontmatter():
    path = "05-Knowledge/Decisions/Byte order mark decision.md"
    assert (GOLDEN_VAULT / path).read_bytes().startswith(b"\xef\xbb\xbf---")
    parsed = golden(path)
    assert parsed.parse_error is None
    assert parsed.type == "decision"
    assert not parsed.body.startswith("\ufeff")


def test_bom_without_frontmatter_is_not_part_of_body():
    parsed = parse_note("00-Inbox/x.md", b"\xef\xbb\xbfHello #tag")
    assert parsed.body == "Hello #tag"
    assert parsed.tags == {"tag"}


def test_crlf_frontmatter_parses():
    path = "05-Knowledge/Lessons/Windows line endings lesson.md"
    assert b"\r\n" in (GOLDEN_VAULT / path).read_bytes()
    parsed = golden(path)
    assert parsed.parse_error is None
    assert parsed.type == "lesson"
    assert all(not str(v).endswith("\r") for v in parsed.frontmatter.values())


def test_empty_file():
    parsed = parse_note("00-Inbox/Empty note.md", b"")
    assert parsed.parse_error is None
    assert parsed.frontmatter == {}
    assert parsed.body == ""
    assert parsed.type == "note"


def test_invalid_utf8_is_flagged_and_does_not_raise():
    data = b"---\ntype: task\n---\nbad \xff\xfe byte [[Target]] #tag\n"
    parsed = parse_note("00-Inbox/x.md", data)
    assert parsed.parse_error and "UTF-8" in parsed.parse_error
    assert parsed.frontmatter == {}
    assert parsed.type == "note"
    assert "\ufffd" in parsed.body
    assert parsed.links == {"target"}
    assert parsed.tags == {"tag"}


# --- Title and promoted fields (2.9) -----------------------------------------------------


@pytest.mark.parametrize(
    ("path", "title"),
    [
        ("02-Work/Tasks/Fix gate latch.md", "Fix gate latch"),
        ("05-Knowledge/Lessons/Lamp sizes #2.md", "Lamp sizes #2"),
        ("00-Inbox/Version 2.0.md", "Version 2.0"),
        ("Top level.md", "Top level"),
    ],
)
def test_title_is_file_name_stem(path, title):
    assert note_stem(path) == title
    assert note("", path).title == title


def test_unknown_keys_and_comments():
    parsed = golden("02-Work/Tasks/Task with unknown keys and comments.md")
    assert parsed.status == "planned"
    assert parsed.frontmatter["estimate_hours"] == 3
    assert parsed.frontmatter["reviewer"] == "neighbour"
    assert list(parsed.frontmatter)[0] == "type"


def test_frontmatter_is_plain_python_data():
    parsed = golden("02-Work/Tasks/Obsidian formatted properties.md")
    fm = parsed.frontmatter
    assert type(fm) is dict
    assert type(fm["tags"]) is list
    assert all(type(item) is str for item in fm["tags"])
    assert type(fm["id"]) is str
    assert fm["created"] == "2026-10-04"
    assert parsed.created == date(2026, 10, 4)


def test_note_id_from_int_and_from_quoted_string():
    assert golden("02-Work/Tasks/Obsidian formatted properties.md").note_id == "20261004111500"
    assert note("---\nid: 20261004111500\n---\n").note_id == "20261004111500"
    assert note("---\nid:\n---\n").note_id is None


@pytest.mark.parametrize("value", ["''", "'   '"])
def test_empty_id_is_no_id(value):
    assert note(f"---\nid: {value}\n---\n").note_id is None


# --- Storable values (2.10 "Values the index must be able to store") -------------------


def _strings(value):
    """Every string inside a parsed value, at any depth (dataclass fields included)."""
    if isinstance(value, ParsedNote):
        for field in ParsedNote.__dataclass_fields__:
            yield from _strings(getattr(value, field))
    elif isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _strings(item)
    elif isinstance(value, list | tuple | set | frozenset):
        for item in value:
            yield from _strings(item)


STORABLE_CASES = [
    "---\ndue: 2026-10-09T23:30:00-02:00\ncreated: 2026-10-09 10:00:00\nd: 2026-10-09\n---\n",
    "---\na: .nan\nb: -.Inf\nc: .INF\nd: 1e400\ne: 1.5\n---\n",
    "---\nlist: [2026-10-09, .nan, {x: 2026-10-09T10:00:00Z}]\n2026-10-09: date key\n---\n",
    "---\ndue: 2026-13-01\n---\n",
]


@pytest.mark.parametrize("path", sorted(EXPECTED_NOTES))
def test_golden_frontmatter_is_json_safe(path):
    parsed = golden(path)
    json.dumps(parsed.frontmatter, allow_nan=False)
    assert not any("\x00" in s for s in _strings(parsed))


@pytest.mark.parametrize("text", STORABLE_CASES)
def test_new_cases_frontmatter_is_json_safe(text):
    parsed = note(text)
    assert parsed.parse_error is None
    json.dumps(parsed.frontmatter, allow_nan=False)


def test_dates_and_timestamps_are_stored_as_written():
    parsed = note(STORABLE_CASES[0])
    assert parsed.frontmatter == {
        "due": "2026-10-09T23:30:00-02:00",
        "created": "2026-10-09 10:00:00",
        "d": "2026-10-09",
    }
    assert parsed.due == date(2026, 10, 9)
    assert parsed.created == date(2026, 10, 9)


def test_non_finite_floats_are_stored_as_yaml_text():
    parsed = note(STORABLE_CASES[1])
    assert parsed.frontmatter == {"a": ".nan", "b": "-.Inf", "c": ".INF", "d": "1e400", "e": 1.5}


def test_nested_dates_and_date_keys_are_text():
    parsed = note(STORABLE_CASES[2])
    assert parsed.frontmatter == {
        "list": ["2026-10-09", ".nan", {"x": "2026-10-09T10:00:00Z"}],
        "2026-10-09": "date key",
    }


def test_quoted_timestamp_string_is_still_an_invalid_date():
    parsed = note("---\ndue: '2026-10-09T10:00:00Z'\n---\n")
    assert parsed.due is None
    assert parsed.invalid_dates == ("due",)


@pytest.mark.parametrize(
    "data",
    [
        b"---\ntype: task\n---\nbody \x00 [[Li\x00nk]] #ta\x00g\n",
        b"no frontmatter \x00 here",
        b"---\ntitle: a\x00b\n---\n",
        b"\x00",
    ],
)
def test_nul_character_is_malformed_and_replaced(data):
    parsed = parse_note("00-Inbox/x.md", data)
    assert parsed.parse_error and "NUL" in parsed.parse_error
    assert parsed.frontmatter == {}
    assert parsed.type == "note"
    assert not any("\x00" in s for s in _strings(parsed))
    assert "\ufffd" in parsed.body


def test_nul_note_keeps_links_and_tags_outside_the_nul():
    parsed = parse_note("00-Inbox/x.md", b"a \x00 [[Link]] #tag\n")
    assert parsed.links == {"link"}
    assert parsed.tags == {"tag"}


def test_invalid_utf8_and_nul_together_report_utf8_and_strip_nul():
    parsed = parse_note("00-Inbox/x.md", b"\xff \x00 text")
    assert "UTF-8" in parsed.parse_error
    assert "\x00" not in parsed.body


# --- Unusable values (2.11) --------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "unusable"),
    [
        ("'[[Harbor Lights]]'", False),
        ("harbor-lights", False),
        ("42", False),
        ("", False),
        ("~", False),
        ("['[[Harbor Lights]]']", True),
        ("{a: 1}", True),
        ("'!!!'", True),
        ("'[[#Goal]]'", True),
        ("'[[]]'", True),
        ("''", True),
    ],
)
def test_unusable_project(value, unusable):
    parsed = note(f"---\nproject: {value}\n---\n")
    assert parsed.unusable_project is unusable
    if unusable:
        assert parsed.project is None


def test_project_absent_is_not_unusable():
    assert note("---\ntype: task\n---\n").unusable_project is False


@pytest.mark.parametrize(
    ("value", "unusable"),
    [
        ("planned", False),
        ("5", False),
        ("true", False),
        ("2026-10-09", False),
        ("", False),
        ("[planned]", True),
        ("{a: 1}", True),
        ("[]", True),
    ],
)
def test_unusable_status(value, unusable):
    parsed = note(f"---\nstatus: {value}\n---\n")
    assert parsed.unusable_status is unusable
    if unusable:
        assert parsed.status is None


def test_status_absent_is_not_unusable():
    assert note("---\ntype: task\n---\n").unusable_status is False


def test_fixture_has_no_unusable_values():
    for path in EXPECTED_NOTES:
        parsed = golden(path)
        assert not parsed.unusable_project, path
        assert not parsed.unusable_status, path


def test_status_and_priority_are_raw_values():
    parsed = note("---\ntype: task\nstatus: Someday\npriority: urgent\n---\n")
    assert parsed.status == "Someday"
    assert parsed.priority == "urgent"


def test_non_string_status_is_kept_as_text():
    parsed = note("---\ntype: task\nstatus: 5\npriority: true\n---\n")
    assert parsed.status == "5"
    assert parsed.priority == "true"


@pytest.mark.parametrize(
    ("value", "invalid"),
    [
        ("low", False),
        ("medium", False),
        ("high", False),
        ("", True),
        ("urgent", True),
        ("High", True),
        ("3", True),
    ],
)
def test_invalid_priority_detail(value, invalid):
    assert note(f"---\npriority: '{value}'\n---\n").invalid_priority is invalid


@pytest.mark.parametrize("value", ["[high]", "{a: b}", "[]", "{}"])
def test_non_scalar_priority_is_invalid(value):
    assert note(f"---\npriority: {value}\n---\n").invalid_priority is True


@pytest.mark.parametrize(
    ("text", "kind"), [("- a\n- b", "list"), ("just text", "scalar"), ("42", "scalar")]
)
def test_non_mapping_frontmatter_message_names_a_plain_kind(text, kind):
    parsed = note(f"---\n{text}\n---\n")
    assert parsed.parse_error == f"frontmatter is a {kind}, not a mapping"


def test_absent_or_null_priority_is_not_invalid():
    assert note("---\ntype: task\n---\n").invalid_priority is False
    assert note("---\npriority:\n---\n").invalid_priority is False
    assert golden("02-Work/Tasks/Task with invalid priority.md").invalid_priority is True


# --- Types (2.10) ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected_type", "unknown"),
    [
        ("type: task", "task", False),
        ("type: 'Task '", "task", False),
        ("type: DAILY", "daily", False),
        ("type: Meeting", "meeting", True),
        ("type: note", "note", False),
        ("type: ' Note '", "note", False),
        ("type: notes", "notes", True),
        ("type: 42", "note", False),
        ("type: [task]", "note", False),
        ("type:", "note", False),
        ("type: ''", "note", False),
        ("type: '   '", "note", False),
        ("other: x", "note", False),
    ],
)
def test_type_rules(line, expected_type, unknown):
    parsed = note(f"---\n{line}\n---\n")
    assert parsed.type == expected_type
    assert parsed.unknown_type is unknown


def test_unknown_and_non_string_type_from_fixture():
    assert golden("00-Inbox/Meeting with unknown type.md").unknown_type is True
    assert golden("00-Inbox/Type that is not a string.md").unknown_type is False


# --- Dates (2.10) ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-10-09", date(2026, 10, 9)),
        ("'2026-10-09'", date(2026, 10, 9)),
        ("2026-10-09T23:30:00-02:00", date(2026, 10, 9)),
        ("2026-10-09T00:30:00+14:00", date(2026, 10, 9)),
        ("2026-10-09 10:00:00", date(2026, 10, 9)),
        ("2026-10-09T10:00:00Z", date(2026, 10, 9)),
    ],
)
def test_valid_dates(raw, expected):
    parsed = note(f"---\ndue: {raw}\n---\n")
    assert parsed.due == expected
    assert parsed.invalid_dates == ()


@pytest.mark.parametrize(
    "raw",
    [
        "next week",
        "2026-13-01",
        "2026-02-30",
        "'2026-02-30'",
        "10/09/2026",
        "20261009",
        "''",
        "' 2026-10-09'",
        "2026-10-9",
        "[2026-10-09]",
        "true",
    ],
)
def test_invalid_dates_are_null_and_reported(raw):
    parsed = note(f"---\ntype: task\nstatus: planned\ndue: {raw}\n---\n")
    assert parsed.parse_error is None
    assert parsed.due is None
    assert parsed.invalid_dates == ("due",)
    assert parsed.status == "planned"


def test_impossible_date_keeps_other_keys_and_raw_value():
    parsed = golden("02-Work/Tasks/Check the ladder rungs.md")
    assert parsed.parse_error is None
    assert parsed.due is None
    assert parsed.frontmatter["due"] == "2026-13-01"
    assert parsed.invalid_dates == ("due",)
    assert (parsed.type, parsed.status, parsed.priority) == ("task", "planned", "medium")
    assert parsed.created == date(2026, 10, 5)
    assert parsed.note_id == "20261005081500"


def test_impossible_timestamp_with_time_is_an_invalid_value():
    parsed = note("---\ntype: task\ndue: 2026-02-30T10:00:00Z\ncreated: 2026-10-01\n---\n")
    assert parsed.parse_error is None
    assert parsed.due is None
    assert parsed.created == date(2026, 10, 1)
    assert parsed.invalid_dates == ("due",)


def test_absent_and_null_dates_are_not_invalid():
    parsed = note("---\ndue:\n---\n")
    assert parsed.due is None and parsed.created is None
    assert parsed.invalid_dates == ()


def test_invalid_dates_cover_created_due_and_decided_in_order():
    parsed = note("---\ndecided: later\ndue: soon\ncreated: never\n---\n")
    assert parsed.invalid_dates == ("created", "due", "decided")


def test_timestamp_date_as_written_from_fixture():
    parsed = golden("02-Work/Tasks/Inspect the pier lamps.md")
    assert parsed.due == date(2026, 10, 9)


# --- Tags (2.10) -------------------------------------------------------------------------


def test_tag_rules_note_from_fixture():
    parsed = golden("05-Knowledge/Lessons/Tag rules.md")
    assert parsed.tags == {"alpha", "beta", "eng", "eng/backend", "v2", "y1984"}
    assert parsed.dropped_tags == ("2024", "two words")


@pytest.mark.parametrize(
    ("body", "tags"),
    [
        ("#start of body", {"start"}),
        ("text\n#line-start", {"line-start"}),
        ("tab\t#tabbed", {"tabbed"}),
        ("end #tag.", {"tag"}),
        ("#a-b_c/d", {"a-b_c/d"}),
        ("#Café and #CAFÉ", {"café"}),
        ("#cafe\u0301", {"café"}),
        ("#日本語", {"日本語"}),
        ("# Heading\n## Sub", set()),
        ("#1984 #2026/10 #/ #//", set()),
        ("#eng// #-", {"eng", "-"}),
        ("#a/b/// #x/", {"a/b", "x"}),
        ("#हिंदी and #नमस्ते", {"हिंदी", "नमस्ते"}),
        ("#a\u0301b", {"áb"}),
        ("#٣", set()),
        ("#x٣", {"x٣"}),
        ("#a²", {"a"}),
        ("[[Note|see #this]] [[ #H]] ![[Embed|#that]]", set()),
        ("text [[Note|see #this]] #kept", {"kept"}),
        ("a#b x,#y (#z)", set()),
        ("`#code` and ``#also code``", set()),
        ("x`code`#glued", set()),
        ("```\n#fenced\n```\n#after", {"after"}),
        ("```code``` #tag\n#later", {"tag", "later"}),
        ("[[A#Heading]] [[#H]] ![[A#^b]] [[x|#alias]]", set()),
        ("[[A]]#glued", set()),
        ("#tag\u00a0next", {"tag"}),
    ],
)
def test_inline_tags(body, tags):
    assert note(body).tags == tags


def test_inline_tags_come_from_body_only():
    parsed = note("---\ntitle: '#notatag'\n---\nBody #real\n")
    assert parsed.tags == {"real"}


@pytest.mark.parametrize(
    ("value", "tags", "dropped"),
    [
        ("[a, B, a]", {"a", "b"}, ()),
        ("'a, #b ,  c  '", {"a", "b", "c"}, ()),
        ("'##double'", set(), ("##double",)),
        ("[2024, v2]", {"v2"}, ("2024",)),
        ("[eng/, '#x/y']", {"eng", "x/y"}, ()),
        ("['a,b']", set(), ("a,b",)),
        ("'a,,b,'", {"a", "b"}, ()),
        ("[a, ~, '']", {"a"}, ()),
        ("[two words, ok]", {"ok"}, ("two words",)),
        ("2024", set(), ("2024",)),
        ("{a: 1, b: 'x, y'}", set(), ("{'a': 1, 'b': 'x, y'}",)),
        ("[[a, b], ok]", {"ok"}, ("['a', 'b']",)),
        ("[हिंदी]", {"हिंदी"}, ()),
        ("[1.5]", set(), ("1.5",)),
        ("[]", set(), ()),
        ("", set(), ()),
    ],
)
def test_frontmatter_tags(value, tags, dropped):
    parsed = note(f"---\ntags: {value}\n---\n")
    assert parsed.tags == tags
    assert parsed.dropped_tags == dropped


def test_only_tags_key_is_read():
    parsed = note("---\ntag: a\ntags: b\nTags: c\n---\n")
    assert parsed.tags == {"b"}


def test_frontmatter_and_inline_tags_merge_and_dedupe():
    parsed = note("---\ntags: [Eng]\n---\n#eng #other\n")
    assert parsed.tags == {"eng", "other"}


# --- Links in frontmatter and body (2.8) -------------------------------------------------


def test_links_from_every_frontmatter_string_value():
    text = (
        "---\n"
        "project: '[[Harbor Lights]]'\n"
        "related: ['[[A]]', 7, '[[B#h]]']\n"
        "nested:\n  inner: see [[C]]\n  more: ['[[D|d]]']\n"
        "'[[Key]]': not a key link\n"
        "---\n"
        "Body [[E]]\n"
    )
    assert note(text).links == {"harbor lights", "a", "b", "c", "d", "e"}


def test_link_set_collapses_spellings():
    parsed = golden("05-Knowledge/Lessons/Repeated links to one target.md")
    assert parsed.links == {"harbor lights"}


# --- Project slug (2.1) ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "slug"),
    [
        ("'[[Harbor Lights]]'", "harbor-lights"),
        ("'[[Harbor Lights|the harbor]]'", "harbor-lights"),
        ("'[[02-Work/Projects/Harbor Lights]]'", "harbor-lights"),
        ("harbor-lights", "harbor-lights"),
        ("LoadUp", "loadup"),
        ("", None),
        ("42", "42"),
        ("['[[Harbor Lights]]']", None),
    ],
)
def test_project_slug_in_parsed_note(value, slug):
    assert note(f"---\nproject: {value}\n---\n").project == slug


# --- Robustness: no input bytes ever raise -----------------------------------------------


def _corpus() -> list[bytes]:
    return [p.read_bytes() for p in sorted(GOLDEN_VAULT.rglob("*.md"))]


def test_truncations_of_every_fixture_file_never_raise():
    for data in _corpus():
        for end in range(len(data) + 1):
            assert isinstance(parse_note("x/y.md", data[:end]), ParsedNote)


def test_random_corruptions_never_raise():
    rng = random.Random(20261009)
    corpus = _corpus()
    specials = [
        b"\x00",
        b"\xff",
        b"\r",
        b"\n",
        b"---\n",
        b"...\n",
        b"[[",
        b"]]",
        b"`",
        b"```\n",
        b"#",
        b"\xef\xbb\xbf",
        b"&a ",
        b"*a",
        b"!!timestamp ",
        b"{",
        b"\t",
        b": ",
    ]
    for _ in range(3000):
        data = bytearray(rng.choice(corpus))
        for _ in range(rng.randint(1, 8)):
            pos = rng.randint(0, len(data))
            action = rng.random()
            if action < 0.4:
                data[pos:pos] = rng.choice(specials)
            elif action < 0.7 and data:
                data[min(pos, len(data) - 1)] = rng.randrange(256)
            else:
                del data[pos : pos + rng.randint(1, 20)]
        assert isinstance(parse_note("x/y.md", bytes(data)), ParsedNote)


def test_random_bytes_never_raise():
    rng = random.Random(42)
    for _ in range(2000):
        data = bytes(rng.randrange(256) for _ in range(rng.randint(0, 200)))
        assert isinstance(parse_note("x/y.md", data), ParsedNote)
        assert isinstance(parse_note("x/y.md", b"---\n" + data + b"\n---\n"), ParsedNote)


def test_deep_nesting_never_raises():
    parsed = note("---\na: " + "[" * 5000 + "]" * 5000 + "\n---\n")
    assert isinstance(parsed, ParsedNote)


# --- Module boundaries -------------------------------------------------------------------


def test_importing_parser_does_not_import_django():
    # Django is not installed in this environment yet (P1-17 adds it). Until then a
    # pass here proves little: an unconditional `import django` would fail with
    # ImportError, but one guarded by try/except leaves no django module loaded and
    # passes. The sys.modules check only bites once Django is installed; until then
    # the source scan in the next test is the effective guard.
    code = (
        "import sys, vault.parser, vault.links, vault.slug, vault.conventions\n"
        "bad = sorted(m for m in sys.modules if m == 'django' or m.startswith('django.'))\n"
        "assert not bad, bad\n"
    )
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=backend, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_vault_package_source_never_mentions_django():
    backend = Path(__file__).resolve().parents[1]
    for name in ("__init__.py", "parser.py", "links.py", "slug.py", "conventions.py"):
        assert "django" not in (backend / "vault" / name).read_text(encoding="utf-8").lower()


# --- conventions.py holds the shared vocabulary (2.3, 2.5, design D) ---------------------


def test_conventions_types_and_folders():
    assert set(conventions.KNOWN_TYPES) == {
        "task",
        "project",
        "decision",
        "lesson",
        "capture",
        "daily",
    }
    assert conventions.DEFAULT_TYPE == "note"
    assert conventions.TYPE_FOLDERS == {
        "task": "02-Work/Tasks",
        "project": "02-Work/Projects",
        "decision": "05-Knowledge/Decisions",
        "lesson": "05-Knowledge/Lessons",
        "capture": "00-Inbox",
        "daily": "01-Daily",
    }
    assert conventions.TEMPLATES_FOLDER == "08-System/Templates"
    assert set(conventions.TEMPLATE_NAMES) == {f"{t}.md" for t in conventions.KNOWN_TYPES}


def test_conventions_status_vocabularies_and_defaults():
    assert conventions.STATUSES == {
        "task": ("inbox", "planned", "in-progress", "blocked", "review", "done", "cancelled"),
        "project": ("active", "paused", "done", "archived"),
        "decision": ("proposed", "accepted", "superseded", "rejected"),
        "lesson": ("active", "archived"),
        "capture": ("inbox", "triaged", "dismissed"),
    }
    assert conventions.DEFAULT_STATUS == {
        "task": "planned",
        "project": "active",
        "decision": "proposed",
        "lesson": "active",
        "capture": "inbox",
    }
    assert conventions.PRIORITIES == ("low", "medium", "high")
    assert conventions.DATE_KEYS == ("created", "due", "decided")


def test_conventions_sanitising_sets():
    assert conventions.CONTROL_CHARACTERS == frozenset([chr(c) for c in range(0x20)] + ["\x7f"])
    assert conventions.WINDOWS_ILLEGAL_CHARACTERS == frozenset('\\/:*?"<>|')
    assert conventions.LINK_BREAKING_CHARACTERS == frozenset("#^[]")
    assert conventions.RESERVED_DEVICE_NAMES == frozenset(
        ["CON", "PRN", "AUX", "NUL"]
        + [f"COM{i}" for i in range(1, 10)]
        + [f"LPT{i}" for i in range(1, 10)]
    )


def test_conventions_attachment_extensions():
    images = ["png", "jpg", "jpeg", "gif", "bmp", "svg", "webp", "avif"]
    audio = ["mp3", "wav", "m4a", "ogg", "flac", "3gp"]
    video = ["mp4", "webm", "mov", "mkv", "ogv"]
    other = ["pdf", "canvas", "base"]
    assert frozenset(images + audio + video + other) == conventions.ATTACHMENT_EXTENSIONS


def test_conventions_required_keys():
    assert conventions.REQUIRED_KEYS["daily"] == ("type", "created")
    for t in ("task", "project", "decision", "lesson", "capture"):
        assert conventions.REQUIRED_KEYS[t] == ("type", "status", "created")


# --- Re-review: escapes, oversized scalars, !!str, plain strings (2.10) ----------------

_SURROGATE_OR_NUL = re.compile("[\x00\ud800-\udfff]")

ESCAPE_CASES = {
    "nul escape": '---\nx: "a\\0b"\n---\n',
    "u0000 escape": '---\nx: "\\u0000"\n---\n',
    "lone high surrogate": '---\nx: "\\ud800"\n---\n',
    "lone low surrogate": '---\nx: "\\udfff"\n---\n',
    "json-style surrogate pair": '---\nx: "\\ud83d\\ude00"\n---\n',
    "nul in link target": '---\nrel: "[[a\\0b]]"\n---\n',
    "nul in key": '---\n"k\\0": 1\n---\n',
    "surrogate in nested list": '---\nlist: [ok, {deep: "\\udc00"}]\n---\n',
}


def _assert_storable(parsed: ParsedNote) -> None:
    for text in _strings(parsed):
        assert not _SURROGATE_OR_NUL.search(text), repr(text)
        text.encode("utf-8")
    json.dumps(parsed.frontmatter, allow_nan=False)


@pytest.mark.parametrize("case", sorted(ESCAPE_CASES))
def test_escaped_nul_or_surrogate_in_frontmatter_is_malformed(case):
    parsed = note(ESCAPE_CASES[case])
    assert parsed.parse_error
    assert parsed.frontmatter == {}
    assert parsed.type == "note"
    _assert_storable(parsed)


def test_escaped_nul_in_link_never_reaches_a_link_target():
    parsed = note(ESCAPE_CASES["nul in link target"])
    assert all("\x00" not in target for target in parsed.links)


def test_real_astral_character_in_frontmatter_is_fine():
    parsed = note('---\nx: "\\U0001F600 and 😀"\ntags: [ok]\n---\n')
    assert parsed.parse_error is None
    assert parsed.frontmatter["x"] == "😀 and 😀"
    _assert_storable(parsed)


@pytest.mark.parametrize("path", sorted(EXPECTED_NOTES))
def test_golden_notes_are_storable(path):
    _assert_storable(golden(path))


def test_oversized_integer_is_kept_as_text_and_other_keys_kept():
    digits = "9" * 5000
    parsed = note(f"---\ntype: task\nstatus: planned\nbig: {digits}\nid: {digits}\n---\n")
    assert parsed.parse_error is None
    assert parsed.frontmatter["big"] == digits
    assert parsed.note_id == digits
    assert (parsed.type, parsed.status) == ("task", "planned")


def test_normal_integers_still_load_as_int():
    parsed = note("---\na: 42\nb: -7\nc: 0x1F\n---\n")
    assert parsed.frontmatter == {"a": 42, "b": -7, "c": 31}


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("due: !!str 2026-10-09", date(2026, 10, 9)),
        ("due: !!str 2026-13-01", None),
        ("due: !!str next week", None),
    ],
)
def test_explicit_str_tag_is_a_string_for_the_date_rule(line, expected):
    parsed = note(f"---\n{line}\n---\n")
    assert parsed.due == expected
    assert parsed.invalid_dates == (() if expected else ("due",))
    assert type(parsed.frontmatter["due"]) is str


def test_explicit_str_tag_for_other_rules():
    parsed = note("---\ntype: !!str Task\nstatus: !!str 12\ntags: !!str 'a, b'\n---\n")
    assert parsed.type == "task"
    assert parsed.status == "12"
    assert parsed.tags == {"a", "b"}


def test_every_frontmatter_string_is_an_exact_str():
    text = (
        "---\n"
        "due: 2026-10-09T23:30:00-02:00\n"
        "created: 2026-10-05\n"
        "block: |\n  line one\n  line two\n"
        "folded: >\n  folded text\n"
        "quoted: 'single'\n"
        'double: "double"\n'
        "tagged: !foo bar\n"
        "explicit: !!str x\n"
        "'quoted key': 1\n"
        "---\n"
    )
    parsed = note(text)
    assert type(parsed.frontmatter["due"]) is str
    assert type(parsed.frontmatter["block"]) is str
    assert parsed.frontmatter["block"] == "line one\nline two\n"
    for key, value in parsed.frontmatter.items():
        assert type(key) is str, key
        if isinstance(value, str):
            assert type(value) is str, key
