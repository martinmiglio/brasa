"""Tests for brasa.core.deploy — deploy logic."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from brasa.core.config import DeployConfig
from brasa.core.deploy import deploy


@pytest.fixture()
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a minimal project layout and chdir into it."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("# app")
    (src / "utils.py").write_text("# utils")
    (tmp_path / ".env").write_text("SECRET=123")
    (tmp_path / "boot.py").write_text("# boot")
    (tmp_path / "main.py").write_text("# main")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@patch("brasa.core.deploy.shutil.which", return_value="/usr/bin/mpy-cross")
@patch("brasa.core.deploy.mpremote_run")
@patch("brasa.core.deploy.fs_cp")
def test_deploy_romfs(
    mock_fs_cp: MagicMock, mock_mpremote: MagicMock, _mock_which: MagicMock, project_dir: Path
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
    args = mock_mpremote.call_args[0]
    assert args[0] == "/dev/cu.test"
    assert "romfs" in args
    assert "--mpy" in args
    assert "deploy" in args


@patch("brasa.core.deploy.mpremote_run")
@patch("brasa.core.deploy.fs_cp")
def test_deploy_romfs_no_mpy(
    mock_fs_cp: MagicMock, mock_mpremote: MagicMock, project_dir: Path
) -> None:
    """ROMFS deploy without mpy_compile omits --mpy."""
    cfg = DeployConfig(mpy_compile=False)
    deploy("/dev/cu.test", cfg)

    args = mock_mpremote.call_args[0]
    assert "--mpy" not in args
    assert "romfs" in args
    assert "deploy" in args


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
    cp_calls = mock_fs_cp.call_args_list
    copied_srcs = [c[0][1] for c in cp_calls]
    # env_file and boot files.
    assert ".env" in copied_srcs
    assert "boot.py" in copied_srcs
    assert "main.py" in copied_srcs
    # Source files.
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
    mock_fs_cp: MagicMock, mock_mpremote: MagicMock, _mock_which: MagicMock, project_dir: Path
) -> None:
    """Boot files that don't exist on disk are silently skipped."""
    # Remove main.py so only boot.py remains.
    (project_dir / "main.py").unlink()

    cfg = DeployConfig()
    deploy("/dev/cu.test", cfg)

    copied = [c[0][1] for c in mock_fs_cp.call_args_list]
    assert "boot.py" in copied
    assert "main.py" not in copied


@patch("brasa.core.deploy.shutil.which", return_value="/usr/bin/mpy-cross")
@patch("brasa.core.deploy.mpremote_run")
@patch("brasa.core.deploy.fs_cp")
def test_deploy_romfs_temp_dir_cleaned(
    mock_fs_cp: MagicMock, mock_mpremote: MagicMock, _mock_which: MagicMock, project_dir: Path
) -> None:
    """The temp directory is cleaned up after romfs deploy."""
    cfg = DeployConfig()
    deploy("/dev/cu.test", cfg)

    # Extract the tmpdir from the mpremote call.
    args = mock_mpremote.call_args[0]
    tmpdir = args[-1].rstrip("/")
    assert not Path(tmpdir).exists()


@patch("brasa.core.deploy.shutil.which", return_value=None)
@patch("brasa.core.deploy.mpremote_run")
@patch("brasa.core.deploy.fs_cp")
def test_deploy_romfs_errors_when_mpy_cross_missing(
    mock_fs_cp: MagicMock, mock_mpremote: MagicMock, _mock_which: MagicMock, project_dir: Path
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
