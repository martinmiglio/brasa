"""Tests for brasa.core.deploy — deploy logic."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from brasa.core.config import DeployConfig
from brasa.core.deploy import deploy


@patch("brasa.core.deploy.shutil.which", return_value="/usr/bin/mpy-cross")
@patch("brasa.core.deploy.mpremote_run")
@patch("brasa.core.deploy.fs_cp")
def test_deploy_romfs(
    mock_fs_cp: MagicMock,
    mock_mpremote: MagicMock,
    _mock_which: MagicMock,
    project_dir: Path,
) -> None:
    """ROMFS deploy copies boot files then calls mpremote romfs with --mpy."""
    cfg = DeployConfig()
    deploy("/dev/cu.test", cfg)

    # Boot files copied.
    assert call("/dev/cu.test", ".env", ":/") in mock_fs_cp.call_args_list
    assert call("/dev/cu.test", "boot.py", ":/") in mock_fs_cp.call_args_list
    assert call("/dev/cu.test", "main.py", ":/") in mock_fs_cp.call_args_list

    # mpremote romfs called with --mpy.
    mock_mpremote.assert_called_once()
    call_args = mock_mpremote.call_args[0]
    assert "/dev/cu.test" in call_args
    assert "romfs" in call_args
    assert "--mpy" in call_args
    assert "deploy" in call_args


@patch("brasa.core.deploy.mpremote_run")
@patch("brasa.core.deploy.fs_cp")
def test_deploy_romfs_no_mpy(
    mock_fs_cp: MagicMock, mock_mpremote: MagicMock, project_dir: Path
) -> None:
    """ROMFS deploy without mpy_compile omits --mpy."""
    cfg = DeployConfig(mpy_compile=False)
    deploy("/dev/cu.test", cfg)

    call_args = mock_mpremote.call_args[0]
    assert "--mpy" not in call_args
    assert "romfs" in call_args
    assert "deploy" in call_args


@patch("brasa.core.deploy.mpremote_run")
@patch("brasa.core.deploy.fs_cp")
def test_deploy_flat(
    mock_fs_cp: MagicMock, mock_mpremote: MagicMock, project_dir: Path
) -> None:
    """Flat deploy copies all src files to device root."""
    cfg = DeployConfig(romfs=False)
    deploy("/dev/cu.test", cfg)

    # mpremote romfs is NOT called.
    mock_mpremote.assert_not_called()

    # Boot files + source files copied via fs_cp.
    assert call("/dev/cu.test", ".env", ":/") in mock_fs_cp.call_args_list
    assert call("/dev/cu.test", "boot.py", ":/") in mock_fs_cp.call_args_list
    assert call("/dev/cu.test", "main.py", ":/") in mock_fs_cp.call_args_list
    # Source files (paths include src/ prefix, destination is :/).
    copied_srcs = [c[0][1] for c in mock_fs_cp.call_args_list]
    assert any("app.py" in s for s in copied_srcs)
    assert any("utils.py" in s for s in copied_srcs)


@patch("brasa.core.deploy.fs_cp")
def test_deploy_missing_env_file(
    mock_fs_cp: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deploy errors when env_file is missing."""
    src = tmp_path / "src"
    src.mkdir()
    monkeypatch.chdir(tmp_path)

    cfg = DeployConfig()
    with pytest.raises(SystemExit):
        deploy("/dev/cu.test", cfg)

    mock_fs_cp.assert_not_called()


@patch("brasa.core.deploy.shutil.which", return_value="/usr/bin/mpy-cross")
@patch("brasa.core.deploy.mpremote_run")
@patch("brasa.core.deploy.fs_cp")
def test_deploy_skips_missing_boot_files(
    mock_fs_cp: MagicMock,
    mock_mpremote: MagicMock,
    _mock_which: MagicMock,
    project_dir: Path,
) -> None:
    """Boot files that don't exist on disk are silently skipped."""
    # Remove main.py so only boot.py remains.
    (project_dir / "main.py").unlink()

    cfg = DeployConfig()
    deploy("/dev/cu.test", cfg)

    assert call("/dev/cu.test", "boot.py", ":/") in mock_fs_cp.call_args_list
    assert call("/dev/cu.test", "main.py", ":/") not in mock_fs_cp.call_args_list


@patch("brasa.core.deploy.shutil.which", return_value="/usr/bin/mpy-cross")
@patch("brasa.core.deploy.mpremote_run")
@patch("brasa.core.deploy.fs_cp")
def test_deploy_romfs_temp_dir_cleaned(
    mock_fs_cp: MagicMock,
    mock_mpremote: MagicMock,
    _mock_which: MagicMock,
    project_dir: Path,
) -> None:
    """The temp directory is cleaned up after romfs deploy."""
    cfg = DeployConfig()
    deploy("/dev/cu.test", cfg)

    # Extract the tmpdir from the mpremote call (always the last positional arg).
    call_args = mock_mpremote.call_args[0]
    tmpdir = call_args[-1].rstrip("/")
    assert not Path(tmpdir).exists()


@patch("brasa.core.deploy.shutil.which", return_value=None)
@patch("brasa.core.deploy.mpremote_run")
@patch("brasa.core.deploy.fs_cp")
def test_deploy_romfs_errors_when_mpy_cross_missing(
    mock_fs_cp: MagicMock,
    mock_mpremote: MagicMock,
    _mock_which: MagicMock,
    project_dir: Path,
) -> None:
    """Deploy errors when mpy_compile=True but mpy-cross is not on PATH."""
    cfg = DeployConfig()
    with pytest.raises(SystemExit):
        deploy("/dev/cu.test", cfg)

    mock_mpremote.assert_not_called()


def test_deploy_module_does_not_import_port_lock() -> None:
    """deploy module does not import port_lock — locking is the caller's job."""
    import brasa.core.deploy as deploy_mod

    symbols = dir(deploy_mod)
    assert "port_lock" not in symbols
