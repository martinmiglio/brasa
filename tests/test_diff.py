"""Tests for brasa.core.diff — file comparison logic and diff command."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from brasa.cli import app
from brasa.core.config import DeployConfig
from brasa.core.diff import DiffStatus, FileDiff, diff_files, print_diff
from tests.conftest import fake_port_lock

runner = CliRunner()

DEVICE_LS_OUTPUT = """\
       123 boot.py
       456 main.py
       789 helper.py
        42 .env
"""


def _setup_local(
    tmp_path: Path, files: dict[str, str], **kwargs: object
) -> DeployConfig:
    """Create local files in tmp_path/src and return a DeployConfig pointing there."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(exist_ok=True)
    for name, content in files.items():
        (src_dir / name).write_text(content)
    return DeployConfig(src=str(src_dir), **kwargs)  # type: ignore[arg-type]


# ── diff_files (flat / romfs=False) ──────────────────────────────────────────


@patch("brasa.core.diff.fs_cat")
@patch("brasa.core.diff.fs_ls", return_value=DEVICE_LS_OUTPUT)
def test_identical_files_no_diff(
    mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path
) -> None:
    cfg = _setup_local(
        tmp_path, {"boot.py": "# boot", "main.py": "# main"}, romfs=False
    )
    mock_cat.side_effect = lambda _port, path: {
        "/boot.py": "# boot",
        "/main.py": "# main",
    }[path]

    diffs = diff_files("/dev/test", cfg)
    # helper.py is device-only
    assert len(diffs) == 1
    assert diffs[0].status == DiffStatus.DEVICE_ONLY
    assert diffs[0].path == "helper.py"


@patch("brasa.core.diff.fs_cat")
@patch("brasa.core.diff.fs_ls", return_value=DEVICE_LS_OUTPUT)
def test_modified_file(mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path) -> None:
    cfg = _setup_local(
        tmp_path,
        {"boot.py": "# local boot\n", "main.py": "# main", "helper.py": "# helper"},
        romfs=False,
    )
    mock_cat.side_effect = lambda _port, path: {
        "/boot.py": "# device boot\n",
        "/main.py": "# main",
        "/helper.py": "# helper",
    }[path]

    diffs = diff_files("/dev/test", cfg)
    modified = [d for d in diffs if d.status == DiffStatus.MODIFIED]
    assert len(modified) == 1
    assert modified[0].path == "boot.py"
    assert any("device:/boot.py" in line for line in modified[0].diff_lines)


@patch("brasa.core.diff.fs_cat")
@patch("brasa.core.diff.fs_ls", return_value="       10 boot.py\n")
def test_local_only_file(
    mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path
) -> None:
    cfg = _setup_local(
        tmp_path, {"boot.py": "# boot", "extra.py": "# extra"}, romfs=False
    )
    mock_cat.return_value = "# boot"

    diffs = diff_files("/dev/test", cfg)
    local_only = [d for d in diffs if d.status == DiffStatus.LOCAL_ONLY]
    assert len(local_only) == 1
    assert local_only[0].path == "extra.py"


@patch("brasa.core.diff.fs_cat")
@patch("brasa.core.diff.fs_ls", return_value="       10 boot.py\n       20 orphan.py\n")
def test_device_only_file(
    mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path
) -> None:
    cfg = _setup_local(tmp_path, {"boot.py": "# boot"}, romfs=False)
    mock_cat.return_value = "# boot"

    diffs = diff_files("/dev/test", cfg)
    device_only = [d for d in diffs if d.status == DiffStatus.DEVICE_ONLY]
    assert len(device_only) == 1
    assert device_only[0].path == "orphan.py"


@patch("brasa.core.diff.fs_cat")
@patch("brasa.core.diff.fs_ls", return_value="       10 .env\n       20 boot.py\n")
def test_env_excluded(mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path) -> None:
    cfg = _setup_local(tmp_path, {"boot.py": "# boot", ".env": "SECRET=1"}, romfs=False)
    mock_cat.return_value = "# boot"

    diffs = diff_files("/dev/test", cfg)
    assert all(d.path != ".env" for d in diffs)


@patch("brasa.core.diff.fs_cat")
@patch("brasa.core.diff.fs_ls", return_value=DEVICE_LS_OUTPUT)
def test_romfs_false_unchanged(
    mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path
) -> None:
    """romfs=False uses existing flat behavior."""
    cfg = _setup_local(
        tmp_path,
        {"boot.py": "# boot", "main.py": "# main", "helper.py": "# helper"},
        romfs=False,
    )
    mock_cat.side_effect = lambda _port, path: {
        "/boot.py": "# boot",
        "/main.py": "# main",
        "/helper.py": "# helper",
    }[path]

    diffs = diff_files("/dev/test", cfg)
    assert diffs == []


# ── diff_files (ROMFS) ───────────────────────────────────────────────────────


ROOT_LS_ROMFS = """\
       123 boot.py
       456 main.py
        42 .env
"""

ROM_LS = """\
       100 app.mpy
       200 utils.mpy
"""


def _fs_ls_side_effect(root_output: str, rom_output: str | None = None):
    """Return a side_effect function for fs_ls dispatching on path."""

    def _side_effect(_port: str, path: str) -> str:
        if path == "/":
            return root_output
        if path == "/rom/":
            if rom_output is None:
                raise subprocess.CalledProcessError(1, "mpremote")
            return rom_output
        return ""

    return _side_effect


@patch("brasa.core.diff.fs_cat")
@patch("brasa.core.diff.fs_ls")
def test_romfs_all_synced(
    mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path
) -> None:
    """romfs=true, boot files match, .mpy files in /rom/ -> boot files no diff, other files ROMFS."""
    cfg = _setup_local(
        tmp_path,
        {
            "boot.py": "# boot",
            "main.py": "# main",
            "app.py": "# app",
            "utils.py": "# utils",
        },
        romfs=True,
        boot_files=("boot.py", "main.py"),
    )
    mock_ls.side_effect = _fs_ls_side_effect(ROOT_LS_ROMFS, ROM_LS)
    mock_cat.side_effect = lambda _port, path: {
        "/boot.py": "# boot",
        "/main.py": "# main",
    }[path]

    diffs = diff_files("/dev/test", cfg)
    romfs_diffs = [d for d in diffs if d.status == DiffStatus.ROMFS]
    assert len(romfs_diffs) == 2
    assert {d.path for d in romfs_diffs} == {"app.py", "utils.py"}
    # No modified boot files.
    assert not [d for d in diffs if d.status == DiffStatus.MODIFIED]


@patch("brasa.core.diff.fs_cat")
@patch("brasa.core.diff.fs_ls")
def test_romfs_local_only(
    mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path
) -> None:
    """romfs=true, local .py with no .mpy -> LOCAL_ONLY."""
    cfg = _setup_local(
        tmp_path,
        {
            "boot.py": "# boot",
            "main.py": "# main",
            "app.py": "# app",
            "newfile.py": "# new",
        },
        romfs=True,
        boot_files=("boot.py", "main.py"),
    )
    mock_ls.side_effect = _fs_ls_side_effect(ROOT_LS_ROMFS, "       100 app.mpy\n")
    mock_cat.side_effect = lambda _port, path: {
        "/boot.py": "# boot",
        "/main.py": "# main",
    }[path]

    diffs = diff_files("/dev/test", cfg)
    local_only = [d for d in diffs if d.status == DiffStatus.LOCAL_ONLY]
    assert len(local_only) == 1
    assert local_only[0].path == "newfile.py"


@patch("brasa.core.diff.fs_cat")
@patch("brasa.core.diff.fs_ls")
def test_romfs_device_only(
    mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path
) -> None:
    """romfs=true, .mpy with no local .py -> DEVICE_ONLY with .mpy name."""
    cfg = _setup_local(
        tmp_path,
        {"boot.py": "# boot", "main.py": "# main", "app.py": "# app"},
        romfs=True,
        boot_files=("boot.py", "main.py"),
    )
    mock_ls.side_effect = _fs_ls_side_effect(
        ROOT_LS_ROMFS, "       100 app.mpy\n       200 orphan.mpy\n"
    )
    mock_cat.side_effect = lambda _port, path: {
        "/boot.py": "# boot",
        "/main.py": "# main",
    }[path]

    diffs = diff_files("/dev/test", cfg)
    device_only = [d for d in diffs if d.status == DiffStatus.DEVICE_ONLY]
    assert len(device_only) == 1
    assert device_only[0].path == "orphan.mpy"


@patch("brasa.core.diff.fs_cat")
@patch("brasa.core.diff.fs_ls")
def test_romfs_boot_file_modified(
    mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path
) -> None:
    """romfs=true, boot file content differs -> MODIFIED."""
    cfg = _setup_local(
        tmp_path,
        {"boot.py": "# local boot\n", "main.py": "# main", "app.py": "# app"},
        romfs=True,
        boot_files=("boot.py", "main.py"),
    )
    mock_ls.side_effect = _fs_ls_side_effect(ROOT_LS_ROMFS, "       100 app.mpy\n")
    mock_cat.side_effect = lambda _port, path: {
        "/boot.py": "# device boot\n",
        "/main.py": "# main",
    }[path]

    diffs = diff_files("/dev/test", cfg)
    modified = [d for d in diffs if d.status == DiffStatus.MODIFIED]
    assert len(modified) == 1
    assert modified[0].path == "boot.py"
    assert any("device:/boot.py" in line for line in modified[0].diff_lines)


@patch("brasa.core.diff.fs_cat")
@patch("brasa.core.diff.fs_ls")
def test_romfs_no_rom_directory(
    mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path
) -> None:
    """romfs=true, fs_ls('/rom/') raises CalledProcessError -> non-boot LOCAL_ONLY."""
    cfg = _setup_local(
        tmp_path,
        {"boot.py": "# boot", "main.py": "# main", "app.py": "# app"},
        romfs=True,
        boot_files=("boot.py", "main.py"),
    )
    mock_ls.side_effect = _fs_ls_side_effect(ROOT_LS_ROMFS, None)
    mock_cat.side_effect = lambda _port, path: {
        "/boot.py": "# boot",
        "/main.py": "# main",
    }[path]

    diffs = diff_files("/dev/test", cfg)
    local_only = [d for d in diffs if d.status == DiffStatus.LOCAL_ONLY]
    assert len(local_only) == 1
    assert local_only[0].path == "app.py"


@patch("brasa.core.diff.fs_cat")
@patch("brasa.core.diff.fs_ls")
def test_romfs_stale_root_py_files(
    mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path
) -> None:
    """romfs=true, stale .py at root that aren't boot files -> DEVICE_ONLY."""
    root_with_stale = """\
       123 boot.py
       456 main.py
       789 old_app.py
        42 .env
"""
    cfg = _setup_local(
        tmp_path,
        {"boot.py": "# boot", "main.py": "# main", "app.py": "# app"},
        romfs=True,
        boot_files=("boot.py", "main.py"),
    )
    mock_ls.side_effect = _fs_ls_side_effect(root_with_stale, "       100 app.mpy\n")
    mock_cat.side_effect = lambda _port, path: {
        "/boot.py": "# boot",
        "/main.py": "# main",
    }[path]

    diffs = diff_files("/dev/test", cfg)
    device_only = [d for d in diffs if d.status == DiffStatus.DEVICE_ONLY]
    assert len(device_only) == 1
    assert device_only[0].path == "old_app.py"


# ── print_diff ─────────────────────────────────────────────────────────────


def test_print_diff_no_diffs(capsys: pytest.CaptureFixture[str]) -> None:
    print_diff([])
    captured = capsys.readouterr()
    assert "up to date" in captured.err.lower()


def test_print_diff_with_modified(capsys: pytest.CaptureFixture[str]) -> None:
    diffs = [
        FileDiff(
            path="boot.py",
            status=DiffStatus.MODIFIED,
            diff_lines=[
                "--- device:/boot.py\n",
                "+++ local:src/boot.py\n",
                "@@ -1 +1 @@\n",
                "-old\n",
                "+new\n",
            ],
        ),
    ]
    print_diff(diffs)
    captured = capsys.readouterr()
    assert "1 modified" in captured.err


def test_print_diff_with_local_and_device_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    diffs = [
        FileDiff(path="new.py", status=DiffStatus.LOCAL_ONLY, diff_lines=[]),
        FileDiff(path="old.py", status=DiffStatus.DEVICE_ONLY, diff_lines=[]),
    ]
    print_diff(diffs)
    captured = capsys.readouterr()
    assert "Only local: new.py" in captured.err
    assert "Only on device: old.py" in captured.err
    assert "1 local only" in captured.err
    assert "1 device only" in captured.err


def test_print_diff_with_romfs(capsys: pytest.CaptureFixture[str]) -> None:
    """print_diff with ROMFS entries shows 'Deployed (romfs)' and 'romfs' in summary."""
    diffs = [
        FileDiff(path="app.py", status=DiffStatus.ROMFS, diff_lines=[]),
        FileDiff(path="utils.py", status=DiffStatus.ROMFS, diff_lines=[]),
        FileDiff(path="new.py", status=DiffStatus.LOCAL_ONLY, diff_lines=[]),
    ]
    print_diff(diffs)
    captured = capsys.readouterr()
    assert "Deployed (romfs): app.py" in captured.err
    assert "Deployed (romfs): utils.py" in captured.err
    assert "2 romfs" in captured.err
    assert "1 local only" in captured.err


# ── error paths ───────────────────────────────────────────────────────────


@patch(
    "brasa.core.diff.fs_ls", side_effect=subprocess.CalledProcessError(1, "mpremote")
)
def test_diff_device_listing_fails(mock_ls: MagicMock, tmp_path: Path) -> None:
    """diff_files raises SystemExit when fs_ls for the root listing fails."""
    cfg = _setup_local(tmp_path, {"boot.py": "# boot"}, romfs=False)
    with pytest.raises(SystemExit):
        diff_files("/dev/test", cfg)


@patch(
    "brasa.core.diff.fs_cat", side_effect=subprocess.CalledProcessError(1, "mpremote")
)
@patch("brasa.core.diff.fs_ls", return_value="       10 boot.py\n")
def test_diff_handles_device_file_read_error(
    mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path
) -> None:
    """diff_files skips files that cannot be read from the device (fs_cat error)."""
    cfg = _setup_local(tmp_path, {"boot.py": "# boot"}, romfs=False)
    diffs = diff_files("/dev/test", cfg)
    # boot.py is in both local and device, but fs_cat fails — it should be skipped,
    # resulting in no MODIFIED entries.
    assert not any(d.status == DiffStatus.MODIFIED for d in diffs)


# ── diff command wiring ────────────────────────────────────────────────────


@patch("brasa.commands.diff.print_diff")
@patch("brasa.commands.diff.diff_files", return_value=[])
@patch("brasa.commands.diff.resolved_port_lock", fake_port_lock)
@patch(
    "brasa.commands.diff.require_config",
    return_value=MagicMock(deploy=DeployConfig()),
)
def test_diff_command(
    mock_config: MagicMock,
    mock_diff_files: MagicMock,
    mock_print: MagicMock,
) -> None:
    result = runner.invoke(app, ["diff"])
    assert result.exit_code == 0
    mock_config.assert_called_once()
    mock_diff_files.assert_called_once()
    mock_print.assert_called_once()


@patch("brasa.commands.diff.print_diff")
@patch("brasa.commands.diff.diff_files", return_value=[])
@patch("brasa.commands.diff.resolved_port_lock", fake_port_lock)
@patch(
    "brasa.commands.diff.require_config",
    return_value=MagicMock(deploy=DeployConfig()),
)
def test_diff_command_with_port_override(
    mock_config: MagicMock,
    mock_diff_files: MagicMock,
    mock_print: MagicMock,
) -> None:
    result = runner.invoke(app, ["--port", "/dev/cu.manual", "diff"])
    assert result.exit_code == 0
    mock_diff_files.assert_called_once_with("/dev/cu.manual", DeployConfig())
