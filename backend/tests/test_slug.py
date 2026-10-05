"""Tests for vault.slug: plan section 2.1."""

import pytest

from vault.slug import ProjectResolution, project_note_slug, project_slug, resolve_project, slugify


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("LoadUp", "loadup"),
        ("Strato GIDA v2", "strato-gida-v2"),
        ("Harbor Lights", "harbor-lights"),
        ("Night Owl", "night-owl"),
        ("Night-Owl", "night-owl"),
        ("Café Ångström", "cafe-angstrom"),
        ("Cafe\u0301", "cafe"),
        ("ﬁle №1", "file-no1"),
        ("  --a__b--  ", "a-b"),
        ("Straße", "stra-e"),
        ("日本語", ""),
        ("", ""),
        ("v2.0 / beta", "v2-0-beta"),
    ],
)
def test_slugify(text, slug):
    assert slugify(text) == slug


@pytest.mark.parametrize(
    ("value", "slug"),
    [
        ("[[Harbor Lights]]", "harbor-lights"),
        ("[[Harbor Lights|the harbor]]", "harbor-lights"),
        ("[[Harbor Lights\\|the harbor]]", "harbor-lights"),
        ("[[02-Work/Projects/Harbor Lights]]", "harbor-lights"),
        ("[[Harbor Lights#Goal]]", "harbor-lights"),
        ("[[Harbor Lights.md]]", "harbor-lights"),
        ("  [[Harbor Lights]]  ", "harbor-lights"),
        ("![[Harbor Lights]]", "harbor-lights"),
        ("harbor-lights", "harbor-lights"),
        ("Harbor Lights", "harbor-lights"),
        ("loadup", "loadup"),
        ("[[Harbor Lights]] extra", "harbor-lights-extra"),
        ("[[]]", None),
        ("[[#Goal]]", None),
        ("", None),
        ("   ", None),
        ("---", None),
        ("42", "42"),
    ],
)
def test_project_slug(value, slug):
    assert project_slug(value) == slug


@pytest.mark.parametrize(
    ("path", "slug"),
    [
        ("02-Work/Projects/Harbor Lights.md", "harbor-lights"),
        ("02-Work/Projects/Night-Owl.md", "night-owl"),
        ("Top.md", "top"),
    ],
)
def test_project_note_slug(path, slug):
    assert project_note_slug(path) == slug


PROJECTS = [
    "02-Work/Projects/Harbor Lights.md",
    "02-Work/Projects/Quiet Garden.md",
    "02-Work/Projects/Night Owl.md",
    "02-Work/Projects/Night-Owl.md",
]


def test_resolve_project_unique():
    assert resolve_project("harbor-lights", PROJECTS) == ProjectResolution(
        "resolved", "02-Work/Projects/Harbor Lights.md", ("02-Work/Projects/Harbor Lights.md",)
    )


def test_resolve_project_duplicate_slug_resolves_to_neither():
    result = resolve_project("night-owl", PROJECTS)
    assert result.status == "duplicate"
    assert result.path is None
    assert result.matches == ("02-Work/Projects/Night Owl.md", "02-Work/Projects/Night-Owl.md")


def test_resolve_project_unknown():
    assert resolve_project("lighthouse-tour", PROJECTS) == ProjectResolution("unknown", None, ())
