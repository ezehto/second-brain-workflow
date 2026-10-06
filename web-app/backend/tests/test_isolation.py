"""Test isolation guards (plan section 6)."""

from pathlib import Path

import pytest
from conftest import assert_outside_real_vault, assert_real_vault_absent


def test_vault_root_is_a_per_test_temp_dir(settings, tmp_path, isolated_vault):
    root = Path(settings.VAULT_ROOT)
    assert root == isolated_vault
    assert tmp_path in root.parents
    assert root.is_dir()
    assert_outside_real_vault(root)


def test_real_vault_mount_is_absent():
    assert not Path("/vault").exists()


def test_guard_fails_when_mount_exists(tmp_path):
    with pytest.raises(pytest.fail.Exception):
        assert_real_vault_absent(tmp_path)


def test_guard_fails_for_path_under_mount(tmp_path):
    inside = tmp_path / "notes" / "a.md"
    with pytest.raises(pytest.fail.Exception):
        assert_outside_real_vault(inside, mount=tmp_path)
    with pytest.raises(pytest.fail.Exception):
        assert_outside_real_vault(tmp_path, mount=tmp_path)
    assert_outside_real_vault(tmp_path, mount=tmp_path / "other")
