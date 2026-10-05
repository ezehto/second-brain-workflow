"""Tests for vault.conformance: plan section 2.11 and the golden fixture's Checker column."""

import ast
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vault import conformance, conventions

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
GOLDEN = REPO / "fixtures" / "golden-vault"
GOLDEN_VAULT = GOLDEN / "vault"
GOLDEN_README = GOLDEN / "README.md"
INIT_VAULT = REPO / "claude" / "scripts" / "init_vault.py"
CONFORMANCE_SOURCE = BACKEND / "vault" / "conformance.py"

TASK = "02-Work/Tasks/Sample.md"
PROJECT_FIELDS = "type: project\nstatus: active\ncreated: 2026-10-05\nid: 2\n"
GOOD_TASK = "---\ntype: task\nstatus: planned\ncreated: 2026-10-05\nid: 1\n---\nBody\n"


def make_vault(root: Path, files: dict[str, str], templates: bool = True) -> Path:
    """Write `files` (vault-relative path -> text) under root; add the six templates."""
    if templates:
        for name in conventions.TEMPLATE_NAMES:
            files = {f"{conventions.TEMPLATES_FOLDER}/{name}": "template\n", **files}
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def found(root: Path) -> set[tuple[str, str]]:
    return {(f.code, f.path) for f in conformance.check_vault(root)}


def codes_for(tmp_path: Path, path: str, text: str, **more: str) -> set[str]:
    """The codes reported for one note in a minimal vault."""
    root = make_vault(tmp_path, {path: text, **more})
    return {code for code, where in found(root) if where == path}


def note(task_fields: str = "", body: str = "") -> str:
    return f"---\n{task_fields}---\n{body}"


# --- Golden fixture and fresh vault --------------------------------------------------------


def expected_from_readme() -> set[tuple[str, str]]:
    """(code, vault-relative path) pairs from the manifest's Checker column."""
    pairs: set[tuple[str, str]] = set()
    checked = 0
    readme = GOLDEN_README.read_text(encoding="utf-8")
    manifest = readme.split("\n## Manifest\n", 1)[1].split("\n## ", 1)[0]
    for line in manifest.splitlines():
        if not line.startswith("| `vault/"):
            continue
        path_cell, _indexed, _covers, checker, _rule = line[2:].split(" | ", 4)
        if checker == "not checked":
            continue
        checked += 1
        path = path_cell.strip("`").removeprefix("vault/")
        if checker == "none":
            continue
        codes = re.findall(r"[FW][0-9]", checker)
        assert codes, f"unreadable Checker cell {checker!r} for {path}"
        pairs.update((code, path) for code in codes)
    assert checked == 61
    return pairs


def test_golden_vault_reports_exactly_the_readme_codes():
    assert found(GOLDEN_VAULT) == expected_from_readme()


def test_golden_vault_findings_are_unique_and_in_path_then_code_order():
    findings = [(f.code, f.path) for f in conformance.check_vault(GOLDEN_VAULT)]
    assert findings == sorted(expected_from_readme(), key=lambda pair: (pair[1], pair[0]))


def test_golden_vault_exit_code_is_1(capsys):
    assert conformance.main([str(GOLDEN_VAULT)]) == 1
    lines = capsys.readouterr().out.splitlines()
    expected = sorted(expected_from_readme(), key=lambda pair: (pair[1], pair[0]))
    assert [(line[:2], line[3:].split(": ", 1)[0]) for line in lines] == [
        (code, path) for code, path in expected
    ]


def test_module_entry_point_on_golden_vault():
    result = subprocess.run(
        [sys.executable, "-m", "vault.conformance", str(GOLDEN_VAULT)],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    keys = [(line.split(": ")[0].split(" ", 1)[1], line[:2]) for line in result.stdout.splitlines()]
    assert keys == sorted(keys)
    assert result.stderr == ""


def test_fresh_init_vault_passes(tmp_path, capsys):
    git_config = tmp_path / "gitconfig"
    git_config.write_text("[user]\n\tname = Test User\n\temail = test@example.invalid\n")
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": str(git_config),
        "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": str(tmp_path),
    }
    vault = tmp_path / "fresh-vault"
    created = subprocess.run(
        [sys.executable, str(INIT_VAULT), str(vault)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    assert conformance.main([str(vault)]) == 0
    assert capsys.readouterr().out == ""


# --- One focused test per code -------------------------------------------------------------


def test_f1_malformed_frontmatter(tmp_path):
    assert codes_for(tmp_path, TASK, "---\ntype: task\nstatus: planned\n") == {"F1"}


def test_f1_reports_a_non_mapping_document(tmp_path):
    assert codes_for(tmp_path, "00-Inbox/List.md", "---\n- a\n- b\n---\n") == {"F1"}


def test_malformed_note_is_checked_for_f1_and_f5_only(tmp_path):
    text = "---\ntype: task\nstatus: bogus\npriority: urgent\ndue: x\n  bad: [\n---\n"
    assert codes_for(tmp_path, "00-Inbox/Odd #1.md", text) == {"F1", "F5"}


def test_f2_known_type_missing_status(tmp_path):
    assert codes_for(tmp_path, TASK, note("type: task\ncreated: 2026-10-05\nid: 1\n")) == {"F2"}


def test_f2_null_value_counts_as_missing(tmp_path):
    text = note("type: task\nstatus:\ncreated: 2026-10-05\nid: 1\n")
    assert codes_for(tmp_path, TASK, text) == {"F2"}


def test_f2_names_every_missing_key_in_one_line(tmp_path):
    root = make_vault(tmp_path, {TASK: note("type: task\nid: 1\n")})
    [finding] = [f for f in conformance.check_vault(root) if f.path == TASK]
    assert finding.code == "F2"
    assert "status" in finding.message
    assert "created" in finding.message


def test_f2_daily_needs_no_status(tmp_path):
    path = "01-Daily/2026/2026-10-05.md"
    assert codes_for(tmp_path, path, note("type: daily\ncreated: 2026-10-05\nid: 1\n")) == set()


def test_f2_daily_missing_created(tmp_path):
    path = "01-Daily/2026/2026-10-05.md"
    assert codes_for(tmp_path, path, note("type: daily\nid: 1\n")) == {"F2"}


def test_f3_status_outside_vocabulary(tmp_path):
    text = note("type: task\nstatus: someday\ncreated: 2026-10-05\nid: 1\n")
    assert codes_for(tmp_path, TASK, text) == {"F3"}


def test_f3_vocabulary_is_per_type(tmp_path):
    # `inbox` is a task status but not a decision status.
    path = "05-Knowledge/Decisions/Pick.md"
    text = note("type: decision\nstatus: inbox\ncreated: 2026-10-05\nid: 1\n")
    assert codes_for(tmp_path, path, text) == {"F3"}


@pytest.mark.parametrize("value", ["[a, b]", "{a: b}"])
def test_f3_non_scalar_status(tmp_path, value):
    text = note(f"type: task\nstatus: {value}\ncreated: 2026-10-05\nid: 1\n")
    assert codes_for(tmp_path, TASK, text) == {"F3"}


def test_f3_does_not_apply_to_daily_notes(tmp_path):
    path = "01-Daily/2026/2026-10-05.md"
    text = note("type: daily\nstatus: whatever\ncreated: 2026-10-05\nid: 1\n")
    assert codes_for(tmp_path, path, text) == set()


@pytest.mark.parametrize(
    "note_type, folder",
    [
        ("task", "02-Work/Projects"),
        ("project", "02-Work/Tasks"),
        ("decision", "05-Knowledge/Lessons"),
        ("lesson", "05-Knowledge/Decisions"),
        ("capture", "02-Work/Tasks"),
        ("task", "00-Inbox"),
    ],
)
def test_f4_known_type_outside_its_folder(tmp_path, note_type, folder):
    status = conventions.DEFAULT_STATUS[note_type]
    text = note(f"type: {note_type}\nstatus: {status}\ncreated: 2026-10-05\nid: 1\n")
    assert codes_for(tmp_path, f"{folder}/Misplaced.md", text) == {"F4"}


def test_f4_nested_folder_below_the_type_folder_is_fine(tmp_path):
    assert codes_for(tmp_path, "02-Work/Tasks/Sub/Deep.md", GOOD_TASK) == set()


@pytest.mark.parametrize(
    "path",
    [
        "01-Daily/2025/2026-10-05.md",  # year folder does not match
        "01-Daily/2026-10-05.md",  # no year folder
        "01-Daily/2026/Monday.md",  # not a date name
        "01-Daily/2026/2026-10-05 extra.md",
        "02-Work/2026/2026-10-05.md",
    ],
)
def test_f4_daily_outside_year_folder_layout(tmp_path, path):
    text = note("type: daily\ncreated: 2026-10-05\nid: 1\n")
    assert "F4" in codes_for(tmp_path, path, text)


def test_f4_daily_in_place_passes(tmp_path):
    path = "01-Daily/2026/2026-10-05.md"
    assert codes_for(tmp_path, path, note("type: daily\ncreated: 2026-10-05\nid: 1\n")) == set()


@pytest.mark.parametrize("char", list('#^[]:*?"<>|\\') + ["\x01", "\x7f"])
def test_f5_forbidden_character_in_file_name(tmp_path, char):
    assert codes_for(tmp_path, f"02-Work/Tasks/Bad{char}name.md", GOOD_TASK) == {"F5"}


@pytest.mark.parametrize("stem", ["CON", "con", "Com1", "LPT9", "NUL", "aux"])
def test_f5_reserved_device_name(tmp_path, stem):
    assert codes_for(tmp_path, f"02-Work/Tasks/{stem}.md", GOOD_TASK) == {"F5"}


def test_f5_reserved_name_must_be_the_whole_stem(tmp_path):
    assert codes_for(tmp_path, "02-Work/Tasks/Console.md", GOOD_TASK) == set()


def test_f5_checks_the_file_name_not_the_folders(tmp_path):
    assert codes_for(tmp_path, "02-Work/Tasks/Sub #1/Fine.md", GOOD_TASK) == set()


def test_f5_applies_to_notes_without_frontmatter(tmp_path):
    assert codes_for(tmp_path, "00-Inbox/Plain #1.md", "just text\n") == {"F5"}


def test_f6_missing_template_is_reported_at_its_path(tmp_path):
    root = make_vault(tmp_path, {})
    (root / conventions.TEMPLATES_FOLDER / "lesson.md").unlink()
    assert found(root) == {("F6", "08-System/Templates/lesson.md")}


def test_f6_reports_every_template_when_the_folder_is_absent(tmp_path):
    root = make_vault(tmp_path, {"00-Inbox/x.md": "text\n"}, templates=False)
    assert found(root) == {
        ("F6", f"{conventions.TEMPLATES_FOLDER}/{name}") for name in conventions.TEMPLATE_NAMES
    }


@pytest.mark.parametrize("key", conventions.DATE_KEYS)
def test_f7_invalid_date(tmp_path, key):
    fields = {"type": "task", "status": "planned", "created": "2026-10-05", "id": "1"}
    fields[key] = "next week"
    text = note("".join(f"{k}: {v}\n" for k, v in fields.items()))
    assert codes_for(tmp_path, TASK, text) == {"F7"}


def test_f7_calendar_impossible_date_is_invalid(tmp_path):
    text = note("type: task\nstatus: planned\ncreated: 2026-10-05\nid: 1\ndue: 2026-13-01\n")
    assert codes_for(tmp_path, TASK, text) == {"F7"}


def test_f7_timestamp_and_null_are_valid(tmp_path):
    text = note(
        "type: task\nstatus: planned\ncreated: 2026-10-05\nid: 1\n"
        "due: 2026-10-09T23:30:00-02:00\ndecided:\n"
    )
    assert codes_for(tmp_path, TASK, text) == set()


def test_f8_invalid_priority(tmp_path):
    text = note("type: task\nstatus: planned\ncreated: 2026-10-05\nid: 1\npriority: urgent\n")
    assert codes_for(tmp_path, TASK, text) == {"F8"}


@pytest.mark.parametrize("value", ["low", "medium", "high", ""])
def test_f8_valid_or_null_priority(tmp_path, value):
    text = note(f"type: task\nstatus: planned\ncreated: 2026-10-05\nid: 1\npriority: {value}\n")
    assert codes_for(tmp_path, TASK, text) == set()


def test_w1_missing_id(tmp_path):
    text = note("type: task\nstatus: planned\ncreated: 2026-10-05\n")
    assert codes_for(tmp_path, TASK, text) == {"W1"}


def test_w1_empty_id_is_missing(tmp_path):
    text = note('type: task\nstatus: planned\ncreated: 2026-10-05\nid: ""\n')
    assert codes_for(tmp_path, TASK, text) == {"W1"}


def test_w2_duplicate_id_reports_both_notes(tmp_path):
    root = make_vault(tmp_path, {"02-Work/Tasks/A.md": GOOD_TASK, "02-Work/Tasks/B.md": GOOD_TASK})
    assert found(root) == {("W2", "02-Work/Tasks/A.md"), ("W2", "02-Work/Tasks/B.md")}


def test_w2_distinct_ids_are_fine(tmp_path):
    other = GOOD_TASK.replace("id: 1", "id: 2")
    root = make_vault(tmp_path, {"02-Work/Tasks/A.md": GOOD_TASK, "02-Work/Tasks/B.md": other})
    assert found(root) == set()


def test_w3_bare_link_to_duplicated_stem_is_a_warning_with_exit_0(tmp_path, capsys):
    root = make_vault(
        tmp_path,
        {
            "02-Work/Projects/Dup.md": note(PROJECT_FIELDS),
            "05-Knowledge/Decisions/Dup.md": "text\n",
            "02-Work/Tasks/Sample.md": note(
                'type: task\nstatus: planned\ncreated: 2026-10-05\nid: 1\nproject: "[[Dup]]"\n'
            ),
        },
    )
    assert found(root) == {("W3", TASK)}
    assert conformance.main([str(root)]) == 0
    assert capsys.readouterr().out.startswith(f"W3 {TASK}: ")


def test_w3_folder_qualified_link_is_not_ambiguous(tmp_path):
    root = make_vault(
        tmp_path,
        {
            "02-Work/Projects/Dup.md": note(PROJECT_FIELDS),
            "05-Knowledge/Decisions/Dup.md": "text\n",
            "02-Work/Tasks/Sample.md": note(
                "type: task\nstatus: planned\ncreated: 2026-10-05\nid: 1\n"
                'project: "[[02-Work/Projects/Dup]]"\n'
            ),
        },
    )
    assert found(root) == set()


def test_w3_applies_to_triaged_to(tmp_path):
    path = "00-Inbox/Capture.md"
    root = make_vault(
        tmp_path,
        {
            "02-Work/Tasks/Dup.md": "text\n",
            "05-Knowledge/Lessons/Dup.md": "text\n",
            path: note(
                "type: capture\nstatus: triaged\ncreated: 2026-10-05\nid: 1\n"
                'triaged_to: "[[Dup]]"\n'
            ),
        },
    )
    assert found(root) == {("W3", path)}


def test_w3_unique_stem_is_not_ambiguous(tmp_path):
    root = make_vault(
        tmp_path,
        {
            "02-Work/Projects/Solo.md": note(PROJECT_FIELDS),
            "02-Work/Tasks/Sample.md": note(
                'type: task\nstatus: planned\ncreated: 2026-10-05\nid: 1\nproject: "[[Solo]]"\n'
            ),
        },
    )
    assert found(root) == set()


def test_w3_ignored_notes_do_not_make_a_stem_duplicate(tmp_path):
    root = make_vault(
        tmp_path,
        {
            "02-Work/Projects/Solo.md": note(PROJECT_FIELDS),
            ".trash/Solo.md": "text\n",
            "02-Work/Tasks/Sample.md": note(
                'type: task\nstatus: planned\ncreated: 2026-10-05\nid: 1\nproject: "[[Solo]]"\n'
            ),
        },
    )
    assert found(root) == set()


def test_w4_unknown_type_value(tmp_path):
    assert codes_for(tmp_path, "00-Inbox/Odd.md", "---\ntype: Meeting\n---\n") == {"W4"}


def test_w4_explicit_type_note_is_not_unknown(tmp_path):
    assert codes_for(tmp_path, "00-Inbox/Plain.md", "---\ntype: note\n---\n") == set()


def test_w4_non_string_type_is_not_unknown(tmp_path):
    assert codes_for(tmp_path, "00-Inbox/Num.md", "---\ntype: 42\n---\n") == set()


def test_no_usable_type_gets_only_f1_and_f5(tmp_path):
    text = (
        '---\nstatus: bogus\npriority: urgent\ndue: nope\ntags: ["two words"]\n'
        "project: nothing-here\n---\nBody\n"
    )
    assert codes_for(tmp_path, "05-Knowledge/Lessons/No type #1.md", text) == {"F5"}


def test_unknown_type_gets_only_w4_and_f5(tmp_path):
    text = "---\ntype: meeting\nstatus: bogus\npriority: urgent\ndue: nope\ntags: [1]\n---\n"
    assert codes_for(tmp_path, "00-Inbox/Odd #1.md", text) == {"W4", "F5"}


def test_empty_frontmatter_and_no_frontmatter_are_clean(tmp_path):
    root = make_vault(tmp_path, {"00-Inbox/A.md": "---\n---\nBody\n", "00-Inbox/B.md": ""})
    assert found(root) == set()


PROJECT_NOTE = note("type: project\nstatus: active\ncreated: 2026-10-05\nid: 9\n")


def task_with_project(value: str) -> str:
    return note(f"type: task\nstatus: planned\ncreated: 2026-10-05\nid: 1\nproject: {value}\n")


def test_w5_project_that_matches_no_project_note(tmp_path):
    assert codes_for(tmp_path, TASK, task_with_project("nowhere")) == {"W5"}


def test_w5_project_slug_matching_a_project_note_is_fine(tmp_path):
    root = make_vault(
        tmp_path,
        {
            "02-Work/Projects/Harbor Lights.md": PROJECT_NOTE,
            TASK: task_with_project("harbor-lights"),
        },
    )
    assert found(root) == set()


def test_w5_duplicated_project_slug(tmp_path):
    root = make_vault(
        tmp_path,
        {
            "02-Work/Projects/Night Owl.md": PROJECT_NOTE,
            "02-Work/Projects/Night-Owl.md": PROJECT_NOTE.replace("id: 9", "id: 8"),
            TASK: task_with_project("night-owl"),
        },
    )
    assert found(root) == {("W5", TASK)}


@pytest.mark.parametrize("value", ["[a, b]", "{a: b}", '"!!!"'])
def test_w5_project_that_yields_no_slug(tmp_path, value):
    assert codes_for(tmp_path, TASK, task_with_project(value)) == {"W5"}


def test_w5_null_project_is_fine(tmp_path):
    assert codes_for(tmp_path, TASK, task_with_project("")) == set()


def test_w5_only_project_typed_notes_count_as_projects(tmp_path):
    # A decision called "Harbor Lights" is not a project note.
    root = make_vault(
        tmp_path,
        {
            "05-Knowledge/Decisions/Harbor Lights.md": note(
                "type: decision\nstatus: proposed\ncreated: 2026-10-05\nid: 9\n"
            ),
            TASK: task_with_project("harbor-lights"),
        },
    )
    assert found(root) == {("W5", TASK)}


def test_w6_two_dropped_tags_are_one_line(tmp_path):
    text = note(
        'type: task\nstatus: planned\ncreated: 2026-10-05\nid: 1\ntags: ["2024", "two words"]\n'
    )
    root = make_vault(tmp_path, {TASK: text})
    [finding] = [f for f in conformance.check_vault(root) if f.path == TASK]
    assert finding.code == "W6"
    assert "2024" in finding.message
    assert "two words" in finding.message


def test_w6_valid_tags_are_fine(tmp_path):
    text = note("type: task\nstatus: planned\ncreated: 2026-10-05\nid: 1\ntags: [garden, a/b]\n")
    assert codes_for(tmp_path, TASK, text) == set()


# --- Ignore rules (2.9) --------------------------------------------------------------------

BROKEN = "---\n- not a mapping\n---\n"


@pytest.mark.parametrize(
    "path",
    [
        ".obsidian/Note.md",
        ".trash/Note.md",
        ".git/Note.md",
        "02-Work/.hidden/Note.md",
        "02-Work/Tasks/.Note.md",
        "08-System/Templates/Extra.md",
        "02-Work/Tasks/Note.txt",
        "02-Work/Tasks/image.png",
    ],
)
def test_default_ignored_paths_are_not_checked(tmp_path, path):
    root = make_vault(tmp_path, {path: BROKEN})
    assert found(root) == set()


def test_sbignore_file_glob_and_directory(tmp_path):
    root = make_vault(
        tmp_path,
        {
            ".sbignore": "# comment\n\n02-Work/Tasks/One.md\n02-Work/Tasks/Scratch *.md\nDrafts/\n",
            "02-Work/Tasks/One.md": BROKEN,
            "02-Work/Tasks/Scratch pad.md": BROKEN,
            "Drafts/Deep/Note.md": BROKEN,
            "02-Work/Tasks/Kept.md": BROKEN,
        },
    )
    assert found(root) == {("F1", "02-Work/Tasks/Kept.md")}


def test_missing_template_is_checked_even_though_the_folder_is_ignored(tmp_path):
    root = make_vault(tmp_path, {})
    (root / conventions.TEMPLATES_FOLDER / "task.md").unlink()
    assert ("F6", "08-System/Templates/task.md") in found(root)


# --- Output, exit codes and usage errors ---------------------------------------------------


def test_output_lines_are_sorted_by_path_then_code(tmp_path, capsys):
    root = make_vault(
        tmp_path,
        {
            "02-Work/Tasks/B.md": note(
                "type: task\nstatus: bogus\npriority: urgent\ncreated: 2026-10-05\n"
            ),
            "00-Inbox/A.md": BROKEN,
        },
    )
    assert conformance.main([str(root)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert [line.split(":")[0] for line in lines] == [
        "F1 00-Inbox/A.md",
        "F3 02-Work/Tasks/B.md",
        "F8 02-Work/Tasks/B.md",
        "W1 02-Work/Tasks/B.md",
    ]


def test_line_format_is_code_path_message(tmp_path, capsys):
    root = make_vault(tmp_path, {"00-Inbox/A.md": BROKEN})
    conformance.main([str(root)])
    [line] = capsys.readouterr().out.splitlines()
    assert re.fullmatch(r"F1 00-Inbox/A\.md: \S.*", line)


def test_warnings_alone_exit_0_and_are_printed(tmp_path, capsys):
    root = make_vault(tmp_path, {TASK: note("type: task\nstatus: planned\ncreated: 2026-10-05\n")})
    assert conformance.main([str(root)]) == 0
    assert capsys.readouterr().out.startswith(f"W1 {TASK}: ")


def test_a_failure_among_warnings_exits_1(tmp_path):
    root = make_vault(tmp_path, {TASK: note("type: task\ncreated: 2026-10-05\n")})
    assert conformance.main([str(root)]) == 1


def test_missing_directory_is_a_usage_error(tmp_path, capsys):
    assert conformance.main([str(tmp_path / "nope")]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "nope" in captured.err


def test_a_file_is_a_usage_error(tmp_path, capsys):
    target = tmp_path / "file.md"
    target.write_text("x")
    assert conformance.main([str(target)]) == 2
    assert capsys.readouterr().err != ""


def test_no_argument_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as raised:
        conformance.main([])
    assert raised.value.code == 2
    assert capsys.readouterr().err != ""


# --- Read-only and shared rules ------------------------------------------------------------


def snapshot(root: Path) -> dict[str, tuple]:
    state: dict[str, tuple] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        stat = path.lstat()
        content = path.read_bytes() if path.is_file() and not path.is_symlink() else None
        state[rel] = (path.is_dir(), content, stat.st_mtime_ns)
    return state


def test_checker_leaves_the_vault_byte_identical(tmp_path):
    vault = tmp_path / "copy"
    shutil.copytree(GOLDEN_VAULT, vault)
    before = snapshot(vault)
    conformance.main([str(vault)])
    assert snapshot(vault) == before


def test_conformance_source_imports_rules_and_defines_none():
    source = CONFORMANCE_SOURCE.read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert not imported & {"re", "regex", "yaml", "ruamel", "django"}
    assert {"vault"} <= imported
    lowered = source.lower()
    assert "yaml" not in lowered
    assert ".compile(" not in source
    assert "re.match" not in source
    assert "re.search" not in source
    assert "wikilink_re" not in lowered


# --- Review round: F8, messages, ordering, robustness, ignore dialect, W3 ---------------------

FIELDS = "type: task\nstatus: planned\ncreated: 2026-10-05\nid: 1\n"


@pytest.mark.parametrize("value", ["[high]", "{a: b}"])
def test_f8_non_scalar_priority(tmp_path, value):
    assert codes_for(tmp_path, TASK, note(FIELDS + f"priority: {value}\n")) == {"F8"}


def test_f1_message_is_plain_text_without_library_names(tmp_path):
    root = make_vault(tmp_path, {"00-Inbox/List.md": "---\n- a\n---\n"})
    [finding] = conformance.check_vault(root)
    assert finding.message == "frontmatter is a list, not a mapping"


def test_output_orders_codes_within_a_path_and_templates_among_paths(tmp_path, capsys):
    root = make_vault(
        tmp_path,
        {
            "02-Work/Tasks/Bad #1.md": note("type: task\ncreated: 2026-10-05\nid: 1\n"),
            "09-Archive/Late.md": BROKEN,
        },
    )
    (root / conventions.TEMPLATES_FOLDER / "lesson.md").unlink()
    conformance.main([str(root)])
    lines = capsys.readouterr().out.splitlines()
    assert [line.split(":")[0] for line in lines] == [
        "F2 02-Work/Tasks/Bad #1.md",
        "F5 02-Work/Tasks/Bad #1.md",
        "F6 08-System/Templates/lesson.md",
        "F1 09-Archive/Late.md",
    ]


def test_unreadable_file_stops_the_run_with_exit_2(tmp_path, capsys):
    if os.geteuid() == 0:
        pytest.skip("root can read anything")
    root = make_vault(tmp_path, {"00-Inbox/A.md": BROKEN, "00-Inbox/Locked.md": "x\n"})
    locked = root / "00-Inbox" / "Locked.md"
    locked.chmod(0)
    try:
        assert conformance.main([str(root)]) == 2
    finally:
        locked.chmod(0o644)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Locked.md" in captured.err


def test_unreadable_sbignore_stops_the_run_with_exit_2(tmp_path, capsys):
    root = make_vault(tmp_path, {"00-Inbox/A.md": BROKEN})
    (root / ".sbignore").mkdir()
    assert conformance.main([str(root)]) == 2
    assert ".sbignore" in capsys.readouterr().err


def test_a_note_that_vanishes_after_listing_is_skipped(tmp_path, monkeypatch):
    root = make_vault(tmp_path, {"00-Inbox/A.md": BROKEN})
    real = conformance.note_paths
    monkeypatch.setattr(conformance, "note_paths", lambda r: [*real(r), "00-Inbox/Gone.md"])
    assert found(root) == {("F1", "00-Inbox/A.md")}


def test_symlinks_are_never_notes_and_symlinked_directories_are_not_entered(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "Out.md").write_text(BROKEN)
    root = make_vault(tmp_path / "vault", {"00-Inbox/A.md": BROKEN})
    (root / "00-Inbox" / "Link.md").symlink_to(outside / "Out.md")
    (root / "00-Inbox" / "Dangling.md").symlink_to(outside / "missing.md")
    (root / "Linked").symlink_to(outside, target_is_directory=True)
    assert found(root) == {("F1", "00-Inbox/A.md")}


def test_a_note_extension_in_any_letter_case_is_a_note(tmp_path):
    assert codes_for(tmp_path, "00-Inbox/Upper.MD", BROKEN) == {"F1"}


def test_folder_names_match_case_insensitively(tmp_path):
    path = "01-daily/2026/2026-10-05.md"
    assert codes_for(tmp_path, path, note("type: daily\ncreated: 2026-10-05\nid: 1\n")) == set()
    assert codes_for(tmp_path / "second", "02-WORK/tasks/Case.md", GOOD_TASK) == set()


def test_daily_note_with_upper_case_extension_is_accepted(tmp_path):
    path = "01-Daily/2026/2026-10-05.MD"
    assert codes_for(tmp_path, path, note("type: daily\ncreated: 2026-10-05\nid: 1\n")) == set()


def test_template_names_and_folders_match_case_insensitively(tmp_path):
    root = make_vault(tmp_path, {}, templates=False)
    folder = root / "08-system" / "TEMPLATES"
    folder.mkdir(parents=True)
    for name in conventions.TEMPLATE_NAMES:
        (folder / name.capitalize()).write_text("template\n")
    assert found(root) == set()


def test_templates_folder_is_ignored_in_any_letter_case(tmp_path):
    files = {f"08-SYSTEM/templates/{name}": "x\n" for name in conventions.TEMPLATE_NAMES}
    files["08-SYSTEM/templates/Extra.md"] = BROKEN
    assert found(make_vault(tmp_path, files, templates=False)) == set()


def test_sbignore_bom_crlf_and_case_insensitive_patterns(tmp_path):
    ignore = "\ufeff02-work/tasks/ONE.md  \r\n# comment\r\n\r\n"
    root = make_vault(
        tmp_path,
        {
            ".sbignore": ignore,
            "02-Work/Tasks/One.md": BROKEN,
            "02-Work/Tasks/Two.md": BROKEN,
        },
    )
    (root / ".sbignore").write_bytes(ignore.encode("utf-8"))
    assert found(root) == {("F1", "02-Work/Tasks/Two.md")}


def test_sbignore_patterns_are_anchored_at_the_vault_root(tmp_path):
    root = make_vault(
        tmp_path,
        {
            ".sbignore": "Drafts/\nOne.md\n",
            "Drafts/A.md": BROKEN,
            "x/Drafts/B.md": BROKEN,
            "One.md": BROKEN,
            "x/One.md": BROKEN,
        },
    )
    assert found(root) == {("F1", "x/Drafts/B.md"), ("F1", "x/One.md")}


def test_sbignore_pattern_without_trailing_slash_does_not_ignore_directory_contents(tmp_path):
    root = make_vault(tmp_path, {".sbignore": "Drafts\n", "Drafts/A.md": BROKEN})
    assert found(root) == {("F1", "Drafts/A.md")}


def test_sbignore_wildcards_question_mark_and_sequence_and_star_crosses_slash(tmp_path):
    root = make_vault(
        tmp_path,
        {
            ".sbignore": "a?.md\nb[12].md\nc*z.md\n",
            "ax.md": BROKEN,
            "b1.md": BROKEN,
            "b3.md": BROKEN,
            "c/d/z.md": BROKEN,
        },
    )
    assert found(root) == {("F1", "b3.md")}


def test_sbignore_directory_pattern_may_use_wildcards(tmp_path):
    root = make_vault(
        tmp_path, {".sbignore": "Dra*/\n", "Drafts/A.md": BROKEN, "Keep/B.md": BROKEN}
    )
    assert found(root) == {("F1", "Keep/B.md")}


@pytest.mark.parametrize("status", ["Done", "' done'", "'done '"])
def test_f3_status_comparison_is_exact(tmp_path, status):
    text = note(f"type: task\nstatus: {status}\ncreated: 2026-10-05\nid: 1\n")
    assert codes_for(tmp_path, TASK, text) == {"F3"}


def test_empty_string_status_is_f3_only(tmp_path):
    text = note("type: task\nstatus: ''\ncreated: 2026-10-05\nid: 1\n")
    assert codes_for(tmp_path, TASK, text) == {"F3"}


def test_empty_string_created_is_f7_only(tmp_path):
    text = note("type: task\nstatus: planned\ncreated: ''\nid: 1\n")
    assert codes_for(tmp_path, TASK, text) == {"F7"}


def test_f4_folder_prefix_must_end_at_a_path_boundary(tmp_path):
    assert codes_for(tmp_path, "02-Work/TasksArchive/x.md", GOOD_TASK) == {"F4"}


@pytest.mark.parametrize("path", ["01-Daily/2026/2026-02-30.md", "01-Daily/2026/Sub/2026-10-05.md"])
def test_f4_daily_requires_a_real_date_and_exact_depth(tmp_path, path):
    text = note("type: daily\ncreated: 2026-10-05\nid: 1\n")
    assert codes_for(tmp_path, path, text) == {"F4"}


def test_w2_counts_ids_of_unknown_type_notes_but_reports_only_eligible_ones(tmp_path):
    root = make_vault(
        tmp_path,
        {TASK: GOOD_TASK, "00-Inbox/Odd.md": "---\ntype: meeting\nid: 1\n---\n"},
    )
    assert found(root) == {("W2", TASK), ("W4", "00-Inbox/Odd.md")}


def test_w3_for_a_list_item(tmp_path):
    path = "00-Inbox/Capture.md"
    root = make_vault(
        tmp_path,
        {
            "02-Work/Tasks/Dup.md": "text\n",
            "05-Knowledge/Lessons/Dup.md": "text\n",
            path: note(
                "type: capture\nstatus: triaged\ncreated: 2026-10-05\nid: 1\n"
                'triaged_to: ["[[Dup]]"]\n'
            ),
        },
    )
    assert found(root) == {("W3", path)}


def test_w3_partly_qualified_link_matching_several_notes(tmp_path):
    root = make_vault(
        tmp_path,
        {
            "02-Work/Projects/Dup.md": note(PROJECT_FIELDS),
            "Other/Projects/Dup.md": "text\n",
            TASK: note(FIELDS + 'project: "[[Projects/Dup]]"\n'),
        },
    )
    [finding] = [f for f in conformance.check_vault(root) if f.code == "W3"]
    assert finding.path == TASK
    assert "[[Projects/Dup]]" in finding.message  # the link as written


def test_unresolved_wikilink_project_is_w5_only(tmp_path):
    assert codes_for(tmp_path, TASK, note(FIELDS + 'project: "[[Nope]]"\n')) == {"W5"}


def test_messages_are_whitespace_collapsed(tmp_path):
    root = make_vault(
        tmp_path, {"02-Work/Tasks/A  B.md": GOOD_TASK, "02-Work/Tasks/C.md": GOOD_TASK}
    )
    [finding] = [f for f in conformance.check_vault(root) if f.path.endswith("C.md")]
    assert finding.message == "id 1 is also used by 02-Work/Tasks/A B.md"


def test_each_finding_is_exactly_one_line_even_for_control_characters_in_names(tmp_path, capsys):
    root = make_vault(
        tmp_path, {"02-Work/Tasks/Bad\nname.md": GOOD_TASK, "02-Work/Tasks/Other.md": GOOD_TASK}
    )
    findings = conformance.check_vault(root)
    assert conformance.main([str(root)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(findings) == 3  # F5 on Bad, W2 on both
    assert "Bad\\nname.md" in lines[0]
    assert all(line[:2] in {"F5", "W2"} for line in lines)


def test_output_survives_undecodable_names_under_a_strict_encoding(tmp_path):
    root = make_vault(tmp_path, {"00-Inbox/Caf\u00e9 #1.md": "x\n"})
    bad = os.fsencode(root / "00-Inbox") + b"/bad\xff #2.md"
    with open(bad, "wb") as handle:
        handle.write(b"x\n")
    env = {**os.environ, "PYTHONIOENCODING": "ascii:strict", "LC_ALL": "C"}
    result = subprocess.run(
        [sys.executable, "-m", "vault.conformance", str(root)],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    assert "bad\\udcff #2.md" in result.stdout
    assert len(result.stdout.splitlines()) == 2


def test_sbignore_symlink_is_not_followed(tmp_path):
    outside = tmp_path / "outside-ignore"
    outside.write_text("00-Inbox/A.md\n")
    root = make_vault(tmp_path / "vault", {"00-Inbox/A.md": BROKEN})
    (root / ".sbignore").symlink_to(outside)
    assert found(root) == {("F1", "00-Inbox/A.md")}


def test_a_file_vanishing_between_walk_and_stat_is_skipped(tmp_path, monkeypatch):
    root = make_vault(tmp_path, {"00-Inbox/A.md": BROKEN})
    real_walk = os.walk

    def walk_with_ghost(top, *args, **kwargs):
        for directory, subdirs, files in real_walk(top, *args, **kwargs):
            yield directory, subdirs, [*files, "Ghost.md"]

    monkeypatch.setattr(conformance.os, "walk", walk_with_ghost)
    assert found(root) == {("F1", "00-Inbox/A.md")}


def test_f4_daily_with_a_valid_name_one_level_too_deep(tmp_path):
    path = "01-Daily/2026/2026-10-05.md/Inner.md"
    text = note("type: daily\ncreated: 2026-10-05\nid: 1\n")
    assert codes_for(tmp_path, path, text) == {"F4"}


def test_unlistable_directory_stops_the_run_with_exit_2(tmp_path, capsys):
    if os.geteuid() == 0:
        pytest.skip("root can list anything")
    root = make_vault(tmp_path, {"02-Work/Tasks/locked/Bad.md": BROKEN, "00-Inbox/A.md": BROKEN})
    locked = root / "02-Work" / "Tasks" / "locked"
    locked.chmod(0)
    try:
        assert conformance.main([str(root)]) == 2
    finally:
        locked.chmod(0o755)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert str(locked) in captured.err
    assert "Traceback" not in captured.err


def test_a_directory_vanishing_during_the_walk_is_skipped(tmp_path, monkeypatch):
    root = make_vault(tmp_path, {"00-Inbox/A.md": BROKEN})
    real_walk = os.walk

    def walk_reporting_a_vanished_directory(top, *args, **kwargs):
        kwargs["onerror"](FileNotFoundError(2, "No such file or directory", str(root / "Gone")))
        yield from real_walk(top, *args, **kwargs)

    monkeypatch.setattr(conformance.os, "walk", walk_reporting_a_vanished_directory)
    assert found(root) == {("F1", "00-Inbox/A.md")}


@pytest.mark.parametrize(
    ("value", "shown"),
    [("urgent", "'urgent'"), ("[high]", "['high']")],
)
def test_f8_message_shows_the_priority_as_written(tmp_path, value, shown):
    root = make_vault(tmp_path, {TASK: note(FIELDS + f"priority: {value}\n")})
    [finding] = [f for f in conformance.check_vault(root) if f.code == "F8"]
    assert finding.message == f"priority {shown} is not one of low, medium, high"


def test_f6_symlinked_template_file_counts_as_missing(tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("template\n")
    root = make_vault(tmp_path / "vault", {})
    template = root / conventions.TEMPLATES_FOLDER / "lesson.md"
    template.unlink()
    template.symlink_to(outside)
    assert found(root) == {("F6", "08-System/Templates/lesson.md")}


def test_f6_symlinked_templates_folder_counts_as_missing(tmp_path):
    outside = tmp_path / "outside-templates"
    outside.mkdir()
    for name in conventions.TEMPLATE_NAMES:
        (outside / name).write_text("template\n")
    root = make_vault(tmp_path / "vault", {}, templates=False)
    folder = root / conventions.TEMPLATES_FOLDER
    folder.parent.mkdir(parents=True)
    folder.symlink_to(outside, target_is_directory=True)
    assert found(root) == {
        ("F6", f"{conventions.TEMPLATES_FOLDER}/{name}") for name in conventions.TEMPLATE_NAMES
    }
