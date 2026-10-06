"""Shared fixtures. Test isolation (plan section 6): tests never see the real vault."""

from pathlib import Path

import pytest

REAL_VAULT_MOUNT = Path("/vault")


def assert_real_vault_absent(mount: Path = REAL_VAULT_MOUNT) -> None:
    """Fail loudly if the container has a vault mounted; the test service must not."""
    if mount.exists():
        pytest.fail(f"{mount} exists in the test container; the test service must not mount it")


def assert_outside_real_vault(path: Path, mount: Path = REAL_VAULT_MOUNT) -> None:
    """Fail if path resolves to or under the real vault mount."""
    resolved = Path(path).resolve()
    if resolved == mount or mount in resolved.parents:
        pytest.fail(f"{path} resolves under {mount}")


@pytest.fixture(autouse=True)
def isolated_vault(settings, tmp_path):
    """Per-test temp vault root; the run fails if /vault exists."""
    assert_real_vault_absent()
    root = tmp_path / "vault"
    root.mkdir()
    settings.VAULT_ROOT = str(root)
    return root
