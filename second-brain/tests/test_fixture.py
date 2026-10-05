"""The golden sample vault (P1-06): every required case is present, and the bytes are exact.

Driven by the manifest table in second-brain/fixtures/golden-vault/README.md. This file checks
presence, bytes and agreement between the manifest and expected/index.json. It does
not parse notes: the expected values in index.json were derived by hand from the plan.

It does not check that index.json or the carry-forward outputs follow from the notes.
A wrong link, tag or slug in index.json, or one item wrong consistently across the
carry-forward files, passes here by design. The parser tests (P1-07) and the command
and API carry-forward tests (P1-13, P1-29) are what guard those values.
"""

import fnmatch
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "second-brain" / "fixtures" / "golden-vault"
VAULT = FIXTURE / "vault"
README = FIXTURE / "README.md"
INDEX = FIXTURE / "expected" / "index.json"
CARRY = FIXTURE / "expected" / "carry-forward"
SEEDS = REPO / "second-brain" / "templates"
TEMPLATE_NAMES = ["task", "project", "daily", "decision", "lesson", "capture"]

# The "Fixture must contain" list of plan section 9, P1-06, one id per case.
# Value: minimum number of manifest rows that must cover the id.
REQUIRED = {
    "valid-task": 1,
    "valid-project": 1,
    "valid-daily": 1,
    "valid-decision": 1,
    "valid-lesson": 1,
    "valid-capture": 1,
    "no-frontmatter": 1,
    "malformed-yaml": 1,
    "unterminated-frontmatter": 1,
    "duplicate-keys": 1,
    "duplicate-id": 2,
    "missing-id": 1,
    "unknown-keys-and-comments": 1,
    "obsidian-properties": 1,
    "crlf": 1,
    "bom": 1,
    "empty-file": 1,
    "non-ascii-name": 1,
    "space-name": 1,
    # Every link form of plan section 2.8.
    "link-plain": 1,
    "link-alias": 1,
    "link-escaped-pipe": 1,
    "link-heading": 1,
    "link-block": 1,
    "link-same-note": 1,
    "link-embed": 1,
    "link-folder": 1,
    "link-md-extension": 1,
    "link-attachment": 1,
    "same-name-different-folders": 2,
    "link-ambiguous": 1,
    "link-folder-qualified-duplicate": 1,
    "link-unresolved": 1,
    "link-frontmatter-list": 1,
    "fake-links-and-tags-in-code": 1,
    "tags-inline": 1,
    "tags-frontmatter": 1,
    "task-inbox": 1,
    "task-planned": 1,
    "task-in-progress": 1,
    "task-blocked": 1,
    "task-review": 1,
    "task-done": 1,
    "task-cancelled": 1,
    "due-past": 1,
    "due-today": 1,
    "due-future": 1,
    "project-wikilink": 1,
    "project-folder-wikilink": 1,
    "project-slug": 1,
    "project-note": 2,
    "project-unknown-slug": 1,
    "daily-gap": 2,
    "capture-inbox": 1,
    "capture-triaged": 1,
    "capture-dismissed": 1,
    "template-copy": 6,
    "ignored-obsidian": 1,
    "ignored-trash": 1,
    "ignored-writer-temp": 1,
    "ignored-sbignore": 1,
    "synthetic": 2,
    "carry-forward-new-note": 1,
    "carry-forward-untouched-note": 1,
    "carry-forward-touched-note": 1,
    # Plan section 9, P1-06 "Section 2.10 to 2.12 cases", and review additions.
    "tags-in-links": 1,
    "tag-not-numeric": 1,
    "tag-nested": 1,
    "tag-trailing-slash": 1,
    "tag-mixed-case": 1,
    "tag-not-mid-word": 1,
    "frontmatter-tag-hash": 1,
    "frontmatter-tag-comma-spaces": 1,
    "frontmatter-tag-numeric": 1,
    "frontmatter-tag-whitespace": 1,
    "unknown-type": 1,
    "non-string-type": 1,
    "repeated-link": 1,
    "no-trailing-newline": 1,
    "trailing-blank-lines": 1,
    "invalid-due-planned": 2,
    "timestamp-due": 1,
    "cf-followup-links-task": 1,
    "cf-today-links-task": 1,
    "cf-today-unresolved": 1,
    "cf-duplicate-in-section": 1,
    "cf-same-text-two-sections": 1,
    "cf-checkbox-markers": 1,
    "cf-star-and-indent": 1,
    "blocked-different-due": 2,
    "related-from-blockers": 1,
    "link-nfd": 1,
    "non-mapping-frontmatter": 1,
    "empty-frontmatter": 1,
    "dots-terminator": 1,
    "sbignore-glob": 1,
    "project-duplicate-stem": 1,
    "capture-name": 3,
}

KNOWN_TYPES = {"task", "project", "daily", "decision", "lesson", "capture"}
# Every code of plan section 2.11 except F6 (all templates are present).
CODES_EXPECTED_IN_VAULT = {"F1", "F2", "F3", "F4", "F5", "F7", "F8", "W1", "W2", "W3", "W4", "W5", "W6"}
MALFORMED = ["malformed-yaml", "unterminated-frontmatter", "duplicate-keys", "non-mapping-frontmatter"]

INDEX_FIELDS = {
    "type", "title", "status", "priority", "project", "due", "created",
    "note_id", "tags", "links", "parse_error",
}

# Raw-text patterns a covering file must contain. Presence only, not parsing.
PATTERNS = {
    "link-plain": r"\[\[[^\]|#/^]+\]\]",
    "link-alias": r"\[\[[^\]|#]+\|[^\]]+\]\]",
    "link-escaped-pipe": r"\[\[[^\]]+\\\|[^\]]+\]\]",
    "link-heading": r"\[\[[^\]#]+#[^\^\]][^\]]*\]\]",
    "link-block": r"\[\[[^\]#]+#\^[^\]]+\]\]",
    "link-same-note": r"\[\[#[^\]]+\]\]",
    "link-embed": r"!\[\[[^\]]+\]\]",
    "link-folder": r"\[\[[^\]]+/[^\]]+\]\]",
    "link-md-extension": r"\[\[[^\]]+\.md\]\]",
    "link-attachment": r"\[\[[^\]]+\.(png|pdf)\]\]",
    "link-folder-qualified-duplicate": r"\[\[[^\]]+/[^\]]+\]\]",
    "link-frontmatter-list": r"\n  - \"\[\[",
    "fake-links-and-tags-in-code": r"(?s)```.*\[\[.*#\w.*```",
    "tags-inline": r"(^|\s)#[A-Za-z][\w/-]*",
    "project-wikilink": r"\nproject: \"\[\[[^/\]]+\]\]\"",
    "project-folder-wikilink": r"\nproject: \"\[\[02-Work/Projects/[^\]]+\]\]\"",
    "project-slug": r"\nproject: [a-z0-9-]+\r?\n",
    "unknown-keys-and-comments": r"(?m)^#.*\n(.*\n)*.* # ",
    "tags-in-links": r"(?s)\[\[[^\]#]+#[^\]]+\]\].*\[\[#[^\]]+\]\].*!\[\[[^\]#]+#\^[^\]]+\]\]",
    "tag-not-numeric": r"(?<!\S)#[0-9]+(?!\S).*(?<!\S)#[0-9]+/[0-9]+(?!\S)",
    "tag-nested": r"(^|\s)#[A-Za-z]+/[A-Za-z]+",
    "tag-trailing-slash": r"(^|\s)#[A-Za-z]+/(\s|$)",
    "tag-mixed-case": r"(^|\s)#[A-Z][a-z]*(\s|$)(.*\s)?#[a-z]+(\s|$)",
    "tag-not-mid-word": r"\w#\w",
    "frontmatter-tag-hash": r"\ntags: \"[^\"\n]*#",
    "frontmatter-tag-comma-spaces": r"\ntags: \"[^\"\n]*, ",
    "frontmatter-tag-numeric": r"\ntags: \"[^\"\n]*\b[0-9]+\b",
    "frontmatter-tag-whitespace": r"\ntags: \"[^\"\n]*, [a-z]+ [a-z]+\"",
    "unknown-type": r"\ntype: [A-Z][a-z]+\n",
    "non-string-type": r"\ntype: [0-9]+\n",
    "repeated-link": r"(?is)(?=.*!\[\[harbor lights)(.*?\[\[harbor lights){5}",
    "timestamp-due": r"\ndue: [0-9]{4}-[0-9]{2}-[0-9]{2}T",
    "invalid-due-planned": r"\nstatus: planned\n(.*\n)*due: (next week|2026-13-01)\n",
    "cf-followup-links-task": r"## Follow-ups\n(.*\n)*- \[ \] [^\n]*\[\[Fix gate latch\]\]",
    "cf-today-links-task": r"## Today\n\n- \[ \] \[\[Wire the dock lights\]\]",
    "cf-today-unresolved": r"- \[ \] Ask about \[\[Moonlight budget\]\]",
    "cf-duplicate-in-section": r"- \[ \] Buy more zip ties\n(.*\n)*- \[ \] Buy  more zip ties \n",
    "cf-same-text-two-sections": r"(?s)## Today.*- \[ \] Charge the drill.*## Follow-ups.*- \[ \] Charge the drill",
    "cf-checkbox-markers": r"(?s)- \[x\].*- \[X\].*- \[/\]",
    "cf-star-and-indent": r"(?s)\n {2,}- \[ \] .*\n\* \[ \] ",
    "dots-terminator": r"^---\n(.*\n)*\.\.\.\n",
    "project-duplicate-stem": r"\nproject: \"\[\[[^/\]]+\]\]\"",
}

ROW = re.compile(
    r"^\| `(?P<path>[^`]+)` \| (?P<indexed>yes|no) \| (?P<covers>[^|]*) \| (?P<codes>[^|]*) \|"
)
CODES_CELL = re.compile(r"none|not checked|`[FW][0-9]`(, `[FW][0-9]`)*")


def manifest() -> list[dict]:
    rows = []
    for line in README.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line)
        if m:
            covers = re.findall(r"`([a-z0-9-]+)`", m["covers"])
            rows.append({
                "path": m["path"],
                "indexed": m["indexed"] == "yes",
                "covers": covers,
                "codes_cell": m["codes"].strip(),
                "codes": set(re.findall(r"`([FW][0-9])`", m["codes"])),
            })
    return rows


def index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def rows_covering(bullet: str) -> list[dict]:
    return [r for r in manifest() if bullet in r["covers"]]


def vault_rel(row: dict) -> str:
    assert row["path"].startswith("vault/"), row["path"]
    return row["path"][len("vault/"):]


def reference_date() -> date:
    return date.fromisoformat(index()["reference_date"])


# --- Manifest ---------------------------------------------------------------


def test_manifest_has_rows():
    assert len(manifest()) >= 40


@pytest.mark.parametrize("bullet", sorted(REQUIRED))
def test_every_required_case_is_covered(bullet):
    rows = rows_covering(bullet)
    assert len(rows) >= REQUIRED[bullet], f"{bullet}: {len(rows)} manifest rows, need {REQUIRED[bullet]}"


def test_manifest_paths_exist():
    missing = [r["path"] for r in manifest() if not (FIXTURE / r["path"]).exists()]
    assert not missing


def test_manifest_paths_are_unique():
    paths = [r["path"] for r in manifest()]
    assert len(paths) == len(set(paths))


@pytest.mark.parametrize("folder", ["vault", "expected"])
def test_every_fixture_file_is_in_the_manifest(folder):
    listed = {r["path"] for r in manifest()}
    root = FIXTURE / folder
    on_disk = {p.relative_to(FIXTURE).as_posix() for p in root.rglob("*") if p.is_file()}
    assert on_disk - listed == set(), f"{folder} files missing from the manifest"


def test_indexed_note_count():
    # The plan says "about 40"; the 2.10 to 2.12 cases and the checker codes add the rest.
    indexed = [r for r in manifest() if r["indexed"]]
    assert 40 <= len(indexed) <= 70


def test_ignored_rows_are_not_indexed():
    for r in manifest():
        if any(c.startswith("ignored-") or c == "template-copy" for c in r["covers"]):
            assert not r["indexed"], r["path"]


def test_readme_contents_links_every_section():
    text = README.read_text(encoding="utf-8")
    for heading in re.findall(r"(?m)^## (.+)$", text):
        if heading == "Contents":
            continue
        anchor = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        assert f"[{heading}](#{anchor})" in text, heading


# --- Templates --------------------------------------------------------------


def test_fixture_has_exactly_the_six_templates():
    names = sorted(p.name for p in (VAULT / "08-System" / "Templates").iterdir())
    assert names == sorted(f"{n}.md" for n in TEMPLATE_NAMES)


@pytest.mark.parametrize("name", TEMPLATE_NAMES)
def test_template_is_byte_identical_to_seed(name):
    fixture = (VAULT / "08-System" / "Templates" / f"{name}.md").read_bytes()
    assert fixture == (SEEDS / f"{name}.md").read_bytes()


# --- expected/index.json ----------------------------------------------------


def test_index_reference_date_matches_readme():
    ref = index()["reference_date"]
    assert index()["timezone"] == "Asia/Manila"
    assert f"Reference date: **{ref}**" in README.read_text(encoding="utf-8")


def test_index_covers_exactly_the_indexed_rows():
    indexed = {vault_rel(r) for r in manifest() if r["indexed"]}
    assert set(index()["notes"]) == indexed


@pytest.mark.parametrize("path", sorted(json.loads(INDEX.read_text(encoding="utf-8"))["notes"]) if INDEX.exists() else [])
def test_index_entry_has_every_field(path):
    entry = index()["notes"][path]
    assert set(entry) == INDEX_FIELDS
    assert entry["title"] == Path(path).stem
    assert isinstance(entry["parse_error"], bool)
    assert entry["tags"] == sorted(set(entry["tags"]))
    assert entry["links"] == sorted(set(entry["links"]))
    for key in ("due", "created"):
        if entry[key] is not None:
            date.fromisoformat(entry[key])


def entries_for(bullet: str) -> list[dict]:
    notes = index()["notes"]
    return [notes[vault_rel(r)] for r in rows_covering(bullet)]


@pytest.mark.parametrize("kind", TEMPLATE_NAMES)
def test_valid_type_rows_agree_with_index(kind):
    for e in entries_for(f"valid-{kind}"):
        assert e["type"] == kind and not e["parse_error"]


@pytest.mark.parametrize("bullet", MALFORMED)
def test_malformed_rows_agree_with_index(bullet):
    for e in entries_for(bullet):
        assert e["parse_error"] and e["type"] == "note" and e["note_id"] is None


def test_only_the_malformed_rows_have_parse_errors():
    malformed = {vault_rel(r) for b in MALFORMED for r in rows_covering(b)}
    flagged = {p for p, e in index()["notes"].items() if e["parse_error"]}
    assert flagged == malformed
    assert len(flagged) == 4


def test_empty_frontmatter_is_valid_with_no_keys():
    for r in rows_covering("empty-frontmatter"):
        assert (FIXTURE / r["path"]).read_bytes().startswith(b"---\n---\n")
        e = index()["notes"][vault_rel(r)]
        assert not e["parse_error"] and e["type"] == "note" and e["note_id"] is None
        assert r["codes_cell"] == "none"


def test_unloadable_date_keeps_the_other_keys():
    path = "02-Work/Tasks/Check the ladder rungs.md"
    assert b"\ndue: 2026-13-01\n" in (VAULT / path).read_bytes()
    e = index()["notes"][path]
    assert not e["parse_error"] and e["due"] is None
    assert (e["type"], e["status"], e["created"]) == ("task", "planned", "2026-10-05")
    row = next(r for r in manifest() if r["path"] == "vault/" + path)
    assert row["codes"] == {"F7"}


@pytest.mark.parametrize(
    "status", ["inbox", "planned", "in-progress", "blocked", "review", "done", "cancelled"]
)
def test_task_status_rows_agree_with_index(status):
    for e in entries_for(f"task-{status}"):
        assert e["type"] == "task" and e["status"] == status


@pytest.mark.parametrize("status", ["inbox", "triaged", "dismissed"])
def test_capture_status_rows_agree_with_index(status):
    for e in entries_for(f"capture-{status}"):
        assert e["type"] == "capture" and e["status"] == status


@pytest.mark.parametrize("when", ["past", "today", "future"])
def test_due_rows_agree_with_reference_date(when):
    ref = reference_date()
    for e in entries_for(f"due-{when}"):
        due = date.fromisoformat(e["due"])
        assert {"past": due < ref, "today": due == ref, "future": due > ref}[when]


def test_duplicate_id_rows_share_one_id():
    ids = [e["note_id"] for e in entries_for("duplicate-id")]
    assert ids[0] is not None and len(set(ids)) == 1


def test_missing_id_rows_have_no_id():
    for e in entries_for("missing-id"):
        assert e["note_id"] is None and not e["parse_error"]


def test_project_notes_and_unknown_slug():
    projects = entries_for("project-note")
    assert all(e["type"] == "project" for e in projects)
    for e in entries_for("project-unknown-slug"):
        assert e["project"] is not None


def test_same_name_rows_share_a_stem_in_different_folders():
    by_stem: dict[str, set] = {}
    for r in rows_covering("same-name-different-folders"):
        by_stem.setdefault(Path(r["path"]).stem.casefold(), set()).add(Path(r["path"]).parent)
    assert by_stem and all(len(folders) >= 2 for folders in by_stem.values()), by_stem


def test_daily_gap_rows_leave_a_day_between():
    days = sorted(date.fromisoformat(Path(r["path"]).stem) for r in rows_covering("daily-gap"))
    assert any((b - a).days >= 2 for a, b in zip(days, days[1:]))


def test_invalid_due_rows_are_planned_with_no_due():
    for e in entries_for("invalid-due-planned"):
        assert e["status"] == "planned" and e["due"] is None


def test_unknown_type_is_kept_and_non_string_type_is_note():
    assert all(e["type"] not in KNOWN_TYPES | {"note"} for e in entries_for("unknown-type"))
    assert all(e["type"] == "note" for e in entries_for("non-string-type"))


def test_repeated_link_gives_one_target():
    for e in entries_for("repeated-link"):
        assert len(e["links"]) == 1


def test_tag_rows_have_tags():
    for bullet in ("tags-inline", "tags-frontmatter"):
        for e in entries_for(bullet):
            assert e["tags"], bullet


# --- Bytes ------------------------------------------------------------------


def covered_bytes(bullet: str) -> list[bytes]:
    return [(FIXTURE / r["path"]).read_bytes() for r in rows_covering(bullet)]


@pytest.mark.parametrize("bullet", MALFORMED)
def test_malformed_files_hold_their_defect(bullet):
    for data in covered_bytes(bullet):
        text = data.decode("utf-8")
        lines = text.split("\n")
        assert lines[0] == "---"
        closers = [i for i, ln in enumerate(lines[1:], 1) if ln in ("---", "...")]
        block = lines[1:closers[0]] if closers else []
        if bullet == "unterminated-frontmatter":
            assert not closers
        elif bullet == "duplicate-keys":
            assert sum(ln.startswith("status:") for ln in block) == 2
        elif bullet == "non-mapping-frontmatter":
            assert block and all(ln.startswith("- ") for ln in block)
        elif bullet == "malformed-yaml":
            assert any("[" in ln and "]" not in ln for ln in block)


def test_nfd_link_text_is_decomposed():
    for data in covered_bytes("link-nfd"):
        assert b"Cafe\xcc\x81 lights" in data
        assert unicodedata.normalize("NFC", data.decode("utf-8")) != data.decode("utf-8")


def test_trailing_newline_cases():
    for data in covered_bytes("no-trailing-newline"):
        assert data and not data.endswith(b"\n")
    for data in covered_bytes("trailing-blank-lines"):
        assert data.endswith(b"\n\n\n\n") and not data.endswith(b"\n\n\n\n\n")


def test_capture_names_follow_rule_9():
    unsafe = '\\/:*?"<>|#^[]'
    for r in rows_covering("capture-name"):
        name = Path(r["path"]).stem
        data = (FIXTURE / r["path"]).read_text(encoding="utf-8")
        body = data.split("\n---\n", 1)[1]
        words = " ".join(body.split()[:8])
        words = "".join(" " if c in unsafe else c for c in words)
        words = " ".join(words.split()).rstrip(". ")
        assert name == name[:16] + words, name


def test_crlf_file_uses_crlf_only():
    for data in covered_bytes("crlf"):
        assert b"\r\n" in data
        assert data.count(b"\n") == data.count(b"\r\n"), "bare LF in the CRLF file"


def test_bom_file_starts_with_bom_then_frontmatter():
    for data in covered_bytes("bom"):
        assert data.startswith(b"\xef\xbb\xbf---\n")


def test_empty_file_is_zero_bytes():
    for data in covered_bytes("empty-file"):
        assert data == b""


def test_no_frontmatter_file_does_not_open_with_a_fence():
    for data in covered_bytes("no-frontmatter"):
        assert data and not data.lstrip(b"\xef\xbb\xbf").startswith(b"---")


def test_name_rows():
    for r in rows_covering("non-ascii-name"):
        assert not r["path"].isascii()
    for r in rows_covering("space-name"):
        assert " " in Path(r["path"]).name


def test_non_ascii_names_are_nfc_on_disk():
    import unicodedata

    for p in VAULT.rglob("*"):
        assert unicodedata.is_normalized("NFC", p.name), p


@pytest.mark.parametrize("bullet", sorted(PATTERNS))
def test_covering_files_contain_the_form(bullet):
    for data in covered_bytes(bullet):
        if re.search(PATTERNS[bullet], data.decode("utf-8")):
            return
    pytest.fail(f"no file covering {bullet} contains {PATTERNS[bullet]!r}")


def test_writer_temp_file_is_named_per_plan():
    for r in rows_covering("ignored-writer-temp"):
        assert re.fullmatch(r"\..+\.sbw-tmp-[0-9a-f]{8}", Path(r["path"]).name)


def sbignore_patterns() -> list[str]:
    lines = (VAULT / ".sbignore").read_text(encoding="utf-8").splitlines()
    return [ln for ln in lines if ln and not ln.startswith("#")]


def test_sbignore_lists_each_sbignore_row():
    patterns = sbignore_patterns()
    for r in rows_covering("ignored-sbignore"):
        rel = vault_rel(r)
        assert any(rel == p or (p.endswith("/") and rel.startswith(p)) or fnmatch.fnmatchcase(rel, p)
                   for p in patterns), rel


def test_sbignore_glob_row_is_matched_by_a_wildcard_line():
    globs = [p for p in sbignore_patterns() if "*" in p]
    for r in rows_covering("sbignore-glob"):
        assert any(fnmatch.fnmatchcase(vault_rel(r), g) for g in globs)


def test_vault_holds_nothing_shaped_like_a_secret():
    pattern = re.compile(r"(?i)(password|token|secret)\s*:\s*\S|BEGIN [A-Z ]*PRIVATE KEY")
    for p in VAULT.rglob("*"):
        if p.is_file() and p.suffix != ".png":
            assert not pattern.search(p.read_text(encoding="utf-8")), p


# --- Synthetic files --------------------------------------------------------


def test_synthetic_rows_are_the_two_obsidian_shaped_files():
    rows = rows_covering("synthetic")
    covers = {c for r in rows for c in r["covers"]}
    assert "obsidian-properties" in covers
    assert any(r["path"].startswith("expected/carry-forward/untouched-note/") for r in rows)


# --- Checker codes (plan section 2.11) ------------------------------------


def test_every_row_has_a_checker_cell():
    for r in manifest():
        assert CODES_CELL.fullmatch(r["codes_cell"]), r["path"]
        assert (r["codes_cell"] == "not checked") == (not r["indexed"]), r["path"]


def test_checker_codes_agree_with_index():
    notes = index()["notes"]
    known_ids = [e["note_id"] for e in notes.values() if e["type"] in KNOWN_TYPES and e["note_id"]]
    for r in manifest():
        if not r["indexed"]:
            continue
        e, codes = notes[vault_rel(r)], r["codes"]
        known = e["type"] in KNOWN_TYPES
        assert ("F1" in codes) == e["parse_error"], r["path"]
        assert ("W1" in codes) == (known and e["note_id"] is None), r["path"]
        assert ("W2" in codes) == (known and known_ids.count(e["note_id"]) > 1), r["path"]
        assert ("W4" in codes) == (e["type"] not in KNOWN_TYPES | {"note"}), r["path"]
        if not known:
            assert codes <= {"F1", "F5", "W4"}, r["path"]
        assert ("W4" not in codes) or e["type"] not in {"note"}, r["path"]


def test_vault_exercises_every_checker_code():
    seen = set().union(*(r["codes"] for r in manifest()))
    assert seen == CODES_EXPECTED_IN_VAULT


def test_readme_states_the_vault_exit_code():
    failures = any(c.startswith("F") for r in manifest() for c in r["codes"])
    text = README.read_text(encoding="utf-8")
    assert f"Checker exit code for the whole vault: **{1 if failures else 0}**" in text


# --- Carry-forward scenarios ------------------------------------------------

SECTIONS = ["Done", "Today", "Blockers", "Decisions / Updates", "Follow-ups", "Related Tasks / Projects"]


def scenario(name: str) -> dict:
    return json.loads((CARRY / name / "scenario.json").read_text(encoding="utf-8"))


def split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter including both fences, rest) for a note that opens with ---."""
    assert text.startswith("---\n")
    end = text.index("\n---\n", 3) + len("\n---\n")
    return text[:end], text[end:]


def section_items(body: str) -> dict:
    items, current = {}, None
    for line in body.split("\n"):
        if line.startswith("## "):
            current = line[3:]
            items[current] = []
        elif current is not None and line.strip():
            items[current].append(line)
    return items


@pytest.mark.parametrize("name", ["new-note", "untouched-note", "touched-note"])
def test_carry_forward_scenario_is_complete(name):
    spec = scenario(name)
    assert spec["date"] == index()["reference_date"]
    assert spec["timezone"] == "Asia/Manila"
    assert spec["test_clock"]["SECOND_BRAIN_TEST_MODE"] == "1"
    assert spec["test_clock"]["SECOND_BRAIN_TODAY"] == spec["date"]
    assert (VAULT / spec["previous_daily_note"]).is_file()
    assert not (VAULT / spec["note_path"]).exists(), "the scenario date must have no note in the vault"
    for file in spec["files"].values():
        assert (CARRY / name / file).is_file()


@pytest.mark.parametrize("name", ["new-note", "untouched-note"])
def test_section_order_is_fixed_everywhere(name):
    spec = scenario(name)
    assert list(spec["expected_sections"]) == SECTIONS
    assert set(spec["section_order"]) == set(SECTIONS)
    assert all(v.startswith("Fixed") for v in spec["section_order"].values())
    assert spec["comparison"].startswith("Byte equality")


def test_new_note_body_matches_expected_sections():
    spec = scenario("new-note")
    body = (CARRY / "new-note" / "expected-body.md").read_text(encoding="utf-8")
    assert body.startswith(f"# Standup - {spec['date']}\n")
    assert section_items(body) == spec["expected_sections"]
    assert body.endswith("\n") and not body.endswith("\n\n")
    fm = spec["expected_frontmatter"]
    assert fm["created"] == spec["date"]
    assert re.fullmatch(fm["id_pattern"], spec["date"].replace("-", "") + "000000")
    assert fm["id_pattern"] == "^" + spec["date"].replace("-", "") + "[0-9]{6}$"


def test_untouched_expected_keeps_input_frontmatter_and_fills_the_body():
    spec = scenario("untouched-note")
    note_in = (CARRY / "untouched-note" / "input.md").read_text(encoding="utf-8")
    note_out = (CARRY / "untouched-note" / "expected.md").read_text(encoding="utf-8")
    fm_in, body_in = split_frontmatter(note_in)
    fm_out, body_out = split_frontmatter(note_out)
    assert fm_out == fm_in
    assert section_items(body_out) == spec["expected_sections"]
    new_body = (CARRY / "new-note" / "expected-body.md").read_text(encoding="utf-8")
    assert body_out.lstrip("\n") == new_body


def rendered_template_body(day: str) -> str:
    _, body = split_frontmatter((SEEDS / "daily.md").read_text(encoding="utf-8"))
    return body.replace("{{title}}", day)


def test_untouched_input_is_the_rendered_template_body():
    spec = scenario("untouched-note")
    fm, body = split_frontmatter((CARRY / "untouched-note" / "input.md").read_text(encoding="utf-8"))
    assert "".join(body.split()) == "".join(rendered_template_body(spec["date"]).split())
    assert "\ntype: daily\n" in fm


def test_touched_input_differs_from_the_template_beyond_whitespace():
    spec = scenario("touched-note")
    fm, body = split_frontmatter((CARRY / "touched-note" / "input.md").read_text(encoding="utf-8"))
    assert "".join(body.split()) != "".join(rendered_template_body(spec["date"]).split())
    assert "\ntype: daily\n" in fm
