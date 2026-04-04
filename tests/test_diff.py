"""Tests for brasa.core.diff — file comparison logic and diff command."""

from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from brasa.cli import app
from brasa.core.config import DeployConfig
from brasa.core.diff import DiffStatus, FileDiff, diff_files, print_diff

runner = CliRunner()

DEVICE_LS_OUTPUT = """\
       123 boot.py
       456 main.py
       789 helper.py
        42 .env
"""


def _setup_local(tmp_path: Path, files: dict[str, str]) -> DeployConfig:
    """Create local files in tmp_path/src and return a DeployConfig pointing there."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(exist_ok=True)
    for name, content in files.items():
        (src_dir / name).write_text(content)
    return DeployConfig(src=str(src_dir))


# ── diff_files ─────────────────────────────────────────────────────────────


@patch("brasa.core.diff.fs_cat")
@patch("brasa.core.diff.fs_ls", return_value=DEVICE_LS_OUTPUT)
def test_identical_files_no_diff(
    mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path
) -> None:
    cfg = _setup_local(tmp_path, {"boot.py": "# boot", "main.py": "# main"})
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
    cfg = _setup_local(tmp_path, {"boot.py": "# boot", "extra.py": "# extra"})
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
    cfg = _setup_local(tmp_path, {"boot.py": "# boot"})
    mock_cat.return_value = "# boot"

    diffs = diff_files("/dev/test", cfg)
    device_only = [d for d in diffs if d.status == DiffStatus.DEVICE_ONLY]
    assert len(device_only) == 1
    assert device_only[0].path == "orphan.py"


@patch("brasa.core.diff.fs_cat")
@patch("brasa.core.diff.fs_ls", return_value="       10 .env\n       20 boot.py\n")
def test_env_excluded(mock_ls: MagicMock, mock_cat: MagicMock, tmp_path: Path) -> None:
    cfg = _setup_local(tmp_path, {"boot.py": "# boot", ".env": "SECRET=1"})
    mock_cat.return_value = "# boot"

    diffs = diff_files("/dev/test", cfg)
    assert all(d.path != ".env" for d in diffs)


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


# ── diff command wiring ────────────────────────────────────────────────────


@patch("brasa.commands.diff.print_diff")
@patch("brasa.commands.diff.diff_files", return_value=[])
@patch("brasa.commands.diff.port_lock", return_value=nullcontext())
@patch("brasa.commands.diff.resolve_port", return_value="/dev/cu.test")
@patch(
    "brasa.commands.diff.require_config",
    return_value=MagicMock(deploy=DeployConfig()),
)
def test_diff_command(
    mock_config: MagicMock,
    mock_detect: MagicMock,
    mock_lock: MagicMock,
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
@patch("brasa.commands.diff.port_lock", return_value=nullcontext())
@patch(
    "brasa.commands.diff.require_config",
    return_value=MagicMock(deploy=DeployConfig()),
)
def test_diff_command_with_port_override(
    mock_config: MagicMock,
    mock_lock: MagicMock,
    mock_diff_files: MagicMock,
    mock_print: MagicMock,
) -> None:
    result = runner.invoke(app, ["--port", "/dev/cu.manual", "diff"])
    assert result.exit_code == 0
    mock_diff_files.assert_called_once_with("/dev/cu.manual", DeployConfig())
