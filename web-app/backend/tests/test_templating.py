"""Tests for vault.templating: the placeholder subset of plan section 3.1."""

from datetime import datetime
from pathlib import Path

import pytest

from vault import conventions
from vault.templating import TemplateError, find_child_ci, load_template, render

WHEN = datetime(2026, 10, 6, 9, 5, 7)
GOLDEN_TEMPLATES = (
    Path(__file__).resolve().parents[3]
    / "second-brain/fixtures/golden-vault/vault/08-System/Templates"
)


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{{title}}", "My title"),
        ("{{date}}", "2026-10-06"),
        ("{{time}}", "09:05"),
        ("{{date:YYYY-MM-DD}}", "2026-10-06"),
        ("{{date:YYYYMMDDHHmmss}}", "20261006090507"),
        ("{{time:HH:mm:ss}}", "09:05:07"),
        ("{{date:DD/MM/YYYY}}", "06/10/2026"),
        ("{{time:HH.mm}}", "09.05"),
        ("a {{title}} b {{date}}", "a My title b 2026-10-06"),
    ],
)
def test_subset_is_substituted(template, expected):
    assert render(template, title="My title", when=WHEN) == expected


@pytest.mark.parametrize(
    "token",
    [
        "{{foo}}",
        "{{ title }}",
        "{{Title}}",
        "{{date:}}",
        "{{date:YYYY-Q}}",  # a letter that is not a supported token
        "{{date:dddd}}",
        "{{date:YY}}",
        "{{date:[YYYY]}}",
        "{{time:A}}",
        "{{datetime}}",
        "{{date:MMMM}}",
        "{{date:DDDD}}",
        "{{date:YYYYY}}",
        "{{date:YYYYYYYY}}",
        "{{time:HHH}}",
        "{{time:sss}}",
        "{{date:MMM}}",
        "{{}}",
    ],
)
def test_any_other_token_is_an_error(token):
    with pytest.raises(TemplateError):
        render(f"before {token} after", title="t", when=WHEN)


def test_substituted_text_is_not_rescanned():
    assert render("{{title}}", title="{{nope}}", when=WHEN) == "{{nope}}"


def test_text_without_placeholders_is_unchanged():
    text = "---\ntags: []\n---\n{ not } {{{ either\n"
    assert render(text, title="t", when=WHEN) == text


def test_every_seed_template_renders():
    for name in conventions.TEMPLATE_NAMES:
        text = (GOLDEN_TEMPLATES / name).read_text(encoding="utf-8")
        assert "{{" not in render(text, title="t", when=WHEN)


def _vault_with_template(root: Path, name: str, data: bytes) -> None:
    folder = root / conventions.TEMPLATES_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)


def test_load_reads_the_vaults_copy(isolated_vault):
    _vault_with_template(isolated_vault, "task.md", b"custom {{title}}\n")
    assert load_template(isolated_vault, "task") == "custom {{title}}\n"


def test_load_drops_bom_and_normalises_crlf(isolated_vault):
    _vault_with_template(isolated_vault, "task.md", b"\xef\xbb\xbfa\r\nb\r\n")
    assert load_template(isolated_vault, "task") == "a\nb\n"


def test_load_matches_folder_and_file_names_in_any_case(isolated_vault):
    folder = isolated_vault / "08-system" / "TEMPLATES"
    folder.mkdir(parents=True)
    (folder / "Task.MD").write_bytes(b"x\n")
    assert load_template(isolated_vault, "task") == "x\n"
    assert find_child_ci(isolated_vault, "08-SYSTEM") == isolated_vault / "08-system"


def test_missing_folder_or_file_or_unknown_type(isolated_vault):
    with pytest.raises(TemplateError):
        load_template(isolated_vault, "task")
    _vault_with_template(isolated_vault, "task.md", b"x")
    with pytest.raises(TemplateError):
        load_template(isolated_vault, "lesson")
    with pytest.raises(TemplateError):
        load_template(isolated_vault, "../task")


def test_invalid_utf8_is_an_error(isolated_vault):
    _vault_with_template(isolated_vault, "task.md", b"\xff\xfe bad")
    with pytest.raises(TemplateError):
        load_template(isolated_vault, "task")


def test_a_symlinked_template_is_refused(isolated_vault, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    _vault_with_template(isolated_vault, "other.md", b"x")
    link = isolated_vault / conventions.TEMPLATES_FOLDER / "task.md"
    link.symlink_to(outside)
    with pytest.raises(TemplateError):
        load_template(isolated_vault, "task")


def test_a_symlinked_templates_folder_is_refused(isolated_vault, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "task.md").write_text("x", encoding="utf-8")
    (isolated_vault / "08-System").mkdir()
    (isolated_vault / "08-System" / "Templates").symlink_to(outside, target_is_directory=True)
    with pytest.raises(TemplateError):
        load_template(isolated_vault, "task")
