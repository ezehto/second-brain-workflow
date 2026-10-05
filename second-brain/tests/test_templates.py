"""The six seed templates must match plan section 3.2 and use only the section 3.1 subset."""

import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML

REPO = Path(__file__).resolve().parents[2]
PLAN = REPO / "docs" / "plan" / "phase-1-foundation.md"
TEMPLATES = REPO / "second-brain" / "templates"
NAMES = ["task", "project", "daily", "decision", "lesson", "capture"]

# Keys and headings of plan section 3.2, in order.
EXPECTED_KEYS = {
    "task": ["type", "id", "status", "priority", "project", "created", "due", "tags"],
    "project": ["type", "id", "status", "created", "tags"],
    "daily": ["type", "id", "created", "tags"],
    "decision": ["type", "id", "status", "project", "created", "decided", "tags"],
    "lesson": ["type", "id", "status", "project", "created", "tags"],
    "capture": ["type", "id", "status", "created", "tags"],
}
EXPECTED_HEADINGS = {
    "task": ["## Description", "## Notes", "## Links"],
    "project": ["## Goal", "## Scope", "## Notes", "## Links"],
    "daily": [
        "# Standup - {{title}}",
        "## Done",
        "## Today",
        "## Blockers",
        "## Decisions / Updates",
        "## Follow-ups",
        "## Related Tasks / Projects",
    ],
    "decision": ["## Context", "## Options considered", "## Decision", "## Consequences", "## Links"],
    "lesson": ["## Context", "## What happened", "## Lesson", "## Apply next time", "## Links"],
    "capture": [],
}
EXPECTED_TYPE = {n: n for n in NAMES}
ALLOWED_PLACEHOLDERS = {"{{title}}", "{{date:YYYY-MM-DD}}", "{{date:YYYYMMDDHHmmss}}"}


def plan_template(name: str) -> str:
    """Return the fenced block that follows the **`name.md`** label in plan section 3.2."""
    text = PLAN.read_text(encoding="utf-8")
    start = text.index("### 3.2 Template content")
    end = text.index("### 3.3 Obsidian settings")
    section = text[start:end]
    m = re.search(
        r"\*\*`" + re.escape(name) + r"\.md`\*\*\n\n```markdown\n(.*?)\n```\n", section, re.S
    )
    assert m, f"template {name} not found in plan section 3.2"
    return m.group(1) + "\n"


def render(text: str) -> str:
    """Render the section 3.1 subset for a fixed moment."""
    values = {"YYYY": "2026", "MM": "10", "DD": "05", "HH": "09", "mm": "30", "ss": "07"}

    def fmt(f: str) -> str:
        for token, val in values.items():
            f = f.replace(token, val)
        return f

    text = text.replace("{{title}}", "Sample Title")
    return re.sub(r"\{\{date:([^}]*)\}\}", lambda m: fmt(m.group(1)), text)


def split_frontmatter(text: str) -> tuple[str, str]:
    assert text.startswith("---\n"), "must start with a frontmatter fence"
    end = text.index("\n---\n", 3)
    return text[4:end], text[end + 5 :]


def load(name: str) -> str:
    return (TEMPLATES / f"{name}.md").read_text(encoding="utf-8")


def test_exactly_six_templates():
    assert sorted(p.name for p in TEMPLATES.glob("*")) == sorted(f"{n}.md" for n in NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_byte_identical_to_plan(name):
    assert (TEMPLATES / f"{name}.md").read_bytes() == plan_template(name).encode("utf-8")


@pytest.mark.parametrize("name", NAMES)
def test_no_table_of_contents(name):
    assert "Contents" not in load(name)


@pytest.mark.parametrize("name", NAMES)
def test_keys_in_order(name):
    fm, _ = split_frontmatter(render(load(name)))
    data = YAML(typ="safe").load(fm)
    assert list(data) == EXPECTED_KEYS[name]
    assert data["type"] == EXPECTED_TYPE[name]


@pytest.mark.parametrize("name", NAMES)
def test_headings(name):
    _, body = split_frontmatter(load(name))
    headings = [ln for ln in body.splitlines() if ln.startswith("#")]
    assert headings == EXPECTED_HEADINGS[name]


@pytest.mark.parametrize("name", NAMES)
def test_only_placeholder_subset(name):
    found = set(re.findall(r"\{\{[^}]*\}\}", load(name)))
    assert found <= ALLOWED_PLACEHOLDERS, found - ALLOWED_PLACEHOLDERS


@pytest.mark.parametrize("name", NAMES)
def test_parses_after_substitution(name):
    rendered = render(load(name))
    assert "{{" not in rendered
    fm, _ = split_frontmatter(rendered)
    data = YAML(typ="safe").load(fm)
    # id becomes an integer after substitution (plan section 2.9).
    assert data["id"] == 20261005093007
    assert str(data["created"]) == "2026-10-05"
    assert data["tags"] == []


def test_empty_keys_are_null():
    for name, keys in {"task": ["project", "due"], "decision": ["project", "decided"], "lesson": ["project"]}.items():
        fm, _ = split_frontmatter(render(load(name)))
        data = YAML(typ="safe").load(fm)
        for key in keys:
            assert data[key] is None, (name, key)


def test_default_status_and_priority():
    defaults = {"task": "planned", "project": "active", "decision": "proposed", "lesson": "active", "capture": "inbox"}
    for name, status in defaults.items():
        fm, _ = split_frontmatter(render(load(name)))
        assert YAML(typ="safe").load(fm)["status"] == status
    fm, _ = split_frontmatter(render(load("task")))
    assert YAML(typ="safe").load(fm)["priority"] == "medium"
    fm, _ = split_frontmatter(render(load("daily")))
    assert "status" not in YAML(typ="safe").load(fm)
