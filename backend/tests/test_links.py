"""Tests for vault.links: plan section 2.8 extraction, normalisation and resolution."""

from pathlib import Path

import pytest

from vault.links import (
    LinkResolution,
    find_wikilinks,
    link_targets,
    mask_code,
    normalize_target,
    note_stem,
    resolve_link,
    split_wikilink,
)

GOLDEN_VAULT = Path(__file__).resolve().parents[2] / "fixtures" / "golden-vault" / "vault"

# --- Normalisation: every row of the 2.8 table ------------------------------------------


@pytest.mark.parametrize(
    ("inner", "expected"),
    [
        ("A", "a"),
        ("A|alias", "a"),
        ("A\\|alias", "a"),
        ("A#Heading", "a"),
        ("A#^block", "a"),
        ("A#Heading|alias", "a"),
        ("#Heading", None),
        ("#^block", None),
        ("", None),
        ("|alias", None),
        ("folder/A", "folder/a"),
        ("Folder\\Sub\\A", "folder/sub/a"),
        ("A.md", "a"),
        ("A.MD", "a"),
        ("folder/A.md#H", "folder/a"),
        ("image.png", None),
        ("file.pdf", None),
        ("Board.canvas", None),
        ("folder/photo.JPG", None),
        ("img.PNG", None),
        ("clip.3gp", None),
        ("Overview.base", None),
        ("Version 2.0", "version 2.0"),
        ("Meeting w. Bob", "meeting w. bob"),
        ("Notes on Node.js", "notes on node.js"),
        ("Report.docx", "report.docx"),
        ("Release v1.2b", "release v1.2b"),
        ("photos.png/Summary", "photos.png/summary"),
        ("  REVIEW   path layout ", "review path layout"),
        ("Tab\there", "tab here"),
        ("Cafe\u0301 lights", "café lights"),
        ("Straße", "strasse"),
        ("   ", None),
    ],
)
def test_normalize_target(inner, expected):
    assert normalize_target(split_wikilink(inner)) == expected


def test_split_wikilink_keeps_raw_target():
    assert split_wikilink("Fix gate latch\\|the latch") == "Fix gate latch"
    assert split_wikilink("A#H|x") == "A"
    assert split_wikilink("A") == "A"


# --- Extraction: code is skipped, embeds count, markdown links do not --------------------


def test_find_wikilinks_returns_inner_text_as_written_in_order():
    text = "[[A]] then ![[B|b]] and [[C#h]]"
    assert find_wikilinks(text) == ["A", "B|b", "C#h"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[[A]] [[a|x]] [[A#H]] ![[A]] [[A.md]]", {"a"}),
        ("`[[code]]` [[real]]", {"real"}),
        ("``[[a ` b]]`` [[real]]", {"real"}),
        ("```\n[[fenced]]\n```\n[[after]]", {"after"}),
        ("~~~\n[[tilde]]\n~~~\n[[after]]", {"after"}),
        ("````\n```\n[[inner]]\n```\n````\n[[after]]", {"after"}),
        ("   ```python\n[[indented fence]]\n   ```\n[[after]]", {"after"}),
        ("    ```\n[[four-space fence]]\n    ```\n[[after]]", {"after"}),
        ("\t~~~\n[[tab fence]]\n\t~~~\n[[after]]", {"after"}),
        # 2.10: a backtick fence's opening line has no further backtick on it.
        ("```code``` and [[x]]\n[[later]]", {"x", "later"}),
        ("  ```code``` [[x]]\n\n[[later]]", {"x", "later"}),
        ("```a` [[in span]]` x\n[[later]]", {"later"}),
        ("- step\n    ```bash\n    [[in fence]]\n\n    ```\n[[after]]", {"after"}),
        ("~~~ a`b\n[[tilde]]\n~~~\n[[after]]", {"after"}),
        ("- item\n  ```\n  [[a]]\n```\n[[after]]", {"after"}),
        ("```\n[[a]]\n```   \t\n[[after]]", {"after"}),
        ("```\n[[a]]\n``` not a close\n[[still code]]", set()),
        ("```\n[[a]]\n``\n[[still code]]", set()),
        ("    plain indented line [[not code]]", {"not code"}),
        ("```\n[[never closed]]\n\n[[still code]]", set()),
        ("```\r\n[[crlf fence]]\r\n```\r\n[[after]]", {"after"}),
        ("~~~\n[[a]]\n```\n[[b]]\n~~~\n[[c]]", {"c"}),
        ("a ` lone backtick [[kept]]", {"kept"}),
        ("`open\n\n[[new paragraph]]` x", {"new paragraph"}),
        ("[the gate](Paint%20the%20gate.md)", set()),
        ("[[lantern-diagram.png]] ![[wiring-plan.pdf]]", set()),
        ("[[#Context]]", set()),
        ("[[broken\nacross lines]]", set()),
        ("| [[Fix gate latch\\|the latch]] |", {"fix gate latch"}),
    ],
)
def test_link_targets(text, expected):
    assert link_targets(text) == expected


LIST_ITEM_FENCES = {
    "tab": (
        "- item\n\t```c\n\t#include <stdio.h>\n\n\t[[Fenced link]] #comment\n\t```\n"
        "- next [[Real]] #real\n"
    ),
    "four spaces": (
        "1. item\n    ```c\n    #include <stdio.h>\n\n    [[Fenced link]] #comment\n    ```\n"
        "2. next [[Real]] #real\n"
    ),
}


@pytest.mark.parametrize("indent", sorted(LIST_ITEM_FENCES))
def test_fence_in_list_item_with_blank_line_is_code(indent):
    from vault.parser import parse_note

    parsed = parse_note("a.md", LIST_ITEM_FENCES[indent].encode())
    assert parsed.links == {"real"}
    assert parsed.tags == {"real"}


@pytest.mark.parametrize(
    ("path", "stem"),
    [("a/b/Note.md", "Note"), ("Note.MD", "Note"), ("a/v1.2", "v1.2"), ("Top.md", "Top")],
)
def test_note_stem(path, stem):
    assert note_stem(path) == stem


def test_mask_code_keeps_line_structure():
    text = "a\n```\ncode\n```\nb `x` c\n"
    masked = mask_code(text)
    assert masked.count("\n") == text.count("\n")
    assert "code" not in masked
    assert "x" not in masked.split("\n")[4].replace("b", "").replace("c", "")


def test_every_link_form_fixture_body_and_frontmatter():
    from vault.parser import parse_note

    path = "05-Knowledge/Lessons/Every link form.md"
    parsed = parse_note(path, (GOLDEN_VAULT / path).read_bytes())
    assert parsed.links == {
        "05-knowledge/lessons/release checklist",
        "café lights need weatherproof plugs",
        "calibrate light sensor",
        "fix gate latch",
        "garden lamp task",
        "harbor lights",
        "moonlight budget",
        "order replacement bulbs",
        "paint the gate",
        "plan lantern rollout",
        "release checklist",
        "review path layout",
        "unresolved from frontmatter",
        "use warm white bulbs",
        "wire the dock lights",
    }


# --- Resolution (2.8 rules 1 to 6) -------------------------------------------------------

PATHS = [
    "02-Work/Tasks/Release checklist.md",
    "05-Knowledge/Lessons/Release checklist.md",
    "02-Work/Projects/Harbor Lights.md",
    "05-Knowledge/Lessons/Café lights need weatherproof plugs.md",
    "02-Work/Tasks/Wire the dock lights.md",
]


def test_bare_unique_target_resolves():
    assert resolve_link("wire the dock lights", PATHS) == LinkResolution(
        "resolved",
        "02-Work/Tasks/Wire the dock lights.md",
        ("02-Work/Tasks/Wire the dock lights.md",),
    )


def test_bare_shared_stem_is_ambiguous_and_picks_shortest_path():
    result = resolve_link("release checklist", PATHS)
    assert result.status == "ambiguous"
    assert result.path == "02-Work/Tasks/Release checklist.md"
    assert result.matches == (
        "02-Work/Tasks/Release checklist.md",
        "05-Knowledge/Lessons/Release checklist.md",
    )


def test_ambiguous_tie_breaks_lexicographically():
    paths = ["b/Same.md", "a/Same.md"]
    result = resolve_link("same", paths)
    assert (result.status, result.path) == ("ambiguous", "a/Same.md")


def test_folder_qualified_target_matches_full_path_or_path_suffix():
    assert resolve_link("05-knowledge/lessons/release checklist", PATHS).path == (
        "05-Knowledge/Lessons/Release checklist.md"
    )
    assert resolve_link("lessons/release checklist", PATHS).status == "resolved"
    assert resolve_link("02-work/projects/harbor lights", PATHS).status == "resolved"


def test_folder_qualified_target_does_not_match_partial_segment():
    assert resolve_link("ssons/release checklist", PATHS).status == "unresolved"


def test_target_with_slash_does_not_fall_back_to_stem():
    assert resolve_link("elsewhere/release checklist", PATHS).status == "unresolved"


def test_unresolved():
    assert resolve_link("moonlight budget", PATHS) == LinkResolution("unresolved", None, ())


def test_resolution_is_case_and_unicode_insensitive():
    target = normalize_target("CAFE\u0301 LIGHTS NEED WEATHERPROOF PLUGS")
    assert resolve_link(target, PATHS).path == (
        "05-Knowledge/Lessons/Café lights need weatherproof plugs.md"
    )


def test_resolution_ignores_non_markdown_paths():
    assert resolve_link("lantern-diagram", ["02-Work/Projects/lantern-diagram.png"]).status == (
        "unresolved"
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # 2.10 "Code regions": a fence also counts after blockquote markers.
        (
            "> [!note] A callout\n> ```bash\n> [[In callout]] #calltag\n>\n> more\n> ```\n"
            "[[After]]",
            {"after"},
        ),
        ("> > ```\n> > [[Nested]]\n> >\n> > ```\n[[After]]", {"after"}),
        (">```\n>[[No space after marker]]\n>\n>```\n[[After]]", {"after"}),
        ("> ~~~\n> [[Tilde in quote]]\n>\n> ~~~\n[[After]]", {"after"}),
        ("> quoted line [[Quoted]]\n> another [[Also quoted]]", {"quoted", "also quoted"}),
        (
            "> ```code``` [[Inline span in quote]]\n>\n> [[Later]]",
            {"inline span in quote", "later"},
        ),
    ],
)
def test_fences_inside_blockquotes_and_callouts(text, expected):
    assert link_targets(text) == expected


def test_callout_fence_tags_are_masked_but_quoted_tags_are_not():
    from vault.parser import parse_note

    text = "> [!note]\n> ```\n> #calltag\n>\n> ```\n> plain #quoted\n"
    assert parse_note("a.md", text.encode()).tags == {"quoted"}


@pytest.mark.parametrize(
    "text",
    [
        "> ```\n> [[In quote fence]]\n\n> [[Still in fence]]\n> ```\n[[After]]",
        "> [!tip]\n> ```python\n> [[A]]\n\n> [[B]]\n> ```\n[[After]]",
        "> > ```\n> > [[A]]\n\n> > [[B]]\n> > ```\n[[After]]",
    ],
)
def test_quoted_fence_with_fully_blank_line_inside_stays_code(text):
    assert link_targets(text) == {"after"}


def test_quoted_fence_with_fully_blank_line_masks_tags():
    from vault.parser import parse_note

    text = "> [!note]\n> ```\n> #include x\n\n> [[Link]] #comment\n> ```\n#after\n"
    parsed = parse_note("a.md", text.encode())
    assert parsed.tags == {"after"}
    assert parsed.links == set()
