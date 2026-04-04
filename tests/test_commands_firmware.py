"""Tests for the firmware CLI sub-app commands."""

import time
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from brasa.cli import app
from brasa.core.config import BrasaConfig, FirmwareConfig
from brasa.core.firmware_index import BoardIndex, FirmwareEntry

runner = CliRunner()

_ENTRIES = (
    FirmwareEntry("ESP32_GENERIC", "", "1.27.0", "20251209", "f1.bin", "url1", "bin"),
    FirmwareEntry("ESP32_GENERIC", "", "1.26.1", "20250911", "f2.bin", "url2", "bin"),
    FirmwareEntry(
        "ESP32_GENERIC", "SPIRAM", "1.27.0", "20251209", "f3.bin", "url3", "bin"
    ),
)
_INDEX = BoardIndex(board="ESP32_GENERIC", entries=_ENTRIES, fetched_at=time.time())


# ── firmware list ───────────────────────────────────────────────────────────


@patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
def test_firmware_list(mock_fetch: MagicMock) -> None:
    result = runner.invoke(app, ["firmware", "list", "--board", "ESP32_GENERIC"])
    assert result.exit_code == 0
    assert "1.27.0" in result.output
    assert "1.26.1" in result.output
    mock_fetch.assert_called_once_with("ESP32_GENERIC", force_refresh=False)


@patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
def test_firmware_list_refresh(mock_fetch: MagicMock) -> None:
    result = runner.invoke(
        app, ["firmware", "list", "--board", "ESP32_GENERIC", "--refresh"]
    )
    assert result.exit_code == 0
    mock_fetch.assert_called_once_with("ESP32_GENERIC", force_refresh=True)


# ── firmware download ───────────────────────────────────────────────────────


@patch("brasa.commands.firmware.download_entry", return_value=Path("/cache/f1.bin"))
@patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
@patch(
    "brasa.commands.firmware.require_config",
    return_value=BrasaConfig(
        firmware=FirmwareConfig(
            board="ESP32_GENERIC", variant="", version="1.27.0", date="20251209"
        )
    ),
)
def test_firmware_download_from_config(
    mock_config: MagicMock, mock_fetch: MagicMock, mock_dl: MagicMock
) -> None:
    result = runner.invoke(app, ["firmware", "download", "--from-config"])
    assert result.exit_code == 0
    mock_dl.assert_called_once()


# ── firmware install ────────────────────────────────────────────────────────


@patch("brasa.commands.firmware.install_firmware")
@patch("brasa.commands.firmware.download_entry", return_value=Path("/cache/f1.bin"))
@patch("brasa.commands.firmware.resolve_port", return_value="/dev/cu.test")
@patch("brasa.commands.firmware.port_lock", return_value=nullcontext())
@patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
@patch(
    "brasa.commands.firmware.require_config",
    return_value=BrasaConfig(
        firmware=FirmwareConfig(
            board="ESP32_GENERIC", variant="", version="1.27.0", date="20251209"
        )
    ),
)
def test_firmware_install_from_config(
    mock_config: MagicMock,
    mock_fetch: MagicMock,
    mock_lock: MagicMock,
    mock_port: MagicMock,
    mock_dl: MagicMock,
    mock_install: MagicMock,
) -> None:
    result = runner.invoke(app, ["firmware", "install", "--from-config"])
    assert result.exit_code == 0
    mock_install.assert_called_once()


# ── firmware pin ────────────────────────────────────────────────────────────


@patch("brasa.commands.firmware.write_pin", return_value=Path("brasa.toml"))
@patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
def test_firmware_pin(mock_fetch: MagicMock, mock_pin: MagicMock) -> None:
    result = runner.invoke(
        app,
        [
            "firmware",
            "pin",
            "--board",
            "ESP32_GENERIC",
            "--variant",
            "",
            "--version",
            "1.27.0",
        ],
    )
    assert result.exit_code == 0
    mock_pin.assert_called_once_with("ESP32_GENERIC", "", "1.27.0", "20251209")


# ── firmware no-args shows help ─────────────────────────────────────────────


def test_firmware_no_args_shows_help() -> None:
    result = runner.invoke(app, ["firmware"])
    assert "list" in result.output
    assert "download" in result.output
    assert "install" in result.output
    assert "pin" in result.output
