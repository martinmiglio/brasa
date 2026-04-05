"""Tests for the flash CLI command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from brasa.cli import app
from brasa.core.config import BrasaConfig, FirmwareConfig
from tests.conftest import fake_port_lock

runner = CliRunner()

_VALID_FIRMWARE = BrasaConfig(
    firmware=FirmwareConfig(
        board="ESP32_GENERIC", variant="", version="1.27.0", date="20251209"
    )
)


# ── flash command happy path ───────────────────────────────────────────────


@patch("brasa.commands.flash.success")
@patch("brasa.commands.flash.flash_firmware")
@patch(
    "brasa.commands.flash.download_firmware",
    return_value=Path("firmware/test.bin"),
)
@patch("brasa.commands.flash.resolved_port_lock", fake_port_lock)
@patch("brasa.commands.flash.require_config", return_value=_VALID_FIRMWARE)
def test_flash_command(
    mock_require: MagicMock,
    mock_download: MagicMock,
    mock_flash: MagicMock,
    mock_success: MagicMock,
) -> None:
    """flash command exits 0 on success."""
    result = runner.invoke(app, ["flash"])
    assert result.exit_code == 0


# ── flash shows deprecation warning ───────────────────────────────────────


@patch("brasa.commands.flash.success")
@patch("brasa.commands.flash.flash_firmware")
@patch(
    "brasa.commands.flash.download_firmware",
    return_value=Path("firmware/test.bin"),
)
@patch("brasa.commands.flash.resolved_port_lock", fake_port_lock)
@patch("brasa.commands.flash.require_config", return_value=_VALID_FIRMWARE)
def test_flash_shows_deprecation_warning(
    mock_require: MagicMock,
    mock_download: MagicMock,
    mock_flash: MagicMock,
    mock_success: MagicMock,
) -> None:
    """flash command output contains deprecation notice."""
    result = runner.invoke(app, ["flash"])
    assert result.exit_code == 0
    assert "deprecated" in result.output.lower()


# ── flash errors on missing version ────────────────────────────────────────


@patch(
    "brasa.commands.flash.require_config",
    return_value=BrasaConfig(
        firmware=FirmwareConfig(board="ESP32_GENERIC", date="20251209")
    ),
)
def test_flash_errors_missing_version(mock_require: MagicMock) -> None:
    """flash command exits 1 when firmware.version is missing."""
    result = runner.invoke(app, ["flash"])
    assert result.exit_code == 1


# ── flash errors on missing date ───────────────────────────────────────────


@patch(
    "brasa.commands.flash.require_config",
    return_value=BrasaConfig(
        firmware=FirmwareConfig(board="ESP32_GENERIC", version="1.27.0")
    ),
)
def test_flash_errors_missing_date(mock_require: MagicMock) -> None:
    """flash command exits 1 when firmware.date is missing."""
    result = runner.invoke(app, ["flash"])
    assert result.exit_code == 1


# ── flash errors when download fails ──────────────────────────────────────


@patch(
    "brasa.commands.flash.download_firmware",
    side_effect=SystemExit(1),
)
@patch("brasa.commands.flash.require_config", return_value=_VALID_FIRMWARE)
def test_flash_command_download_fails(
    mock_require: MagicMock,
    mock_download: MagicMock,
) -> None:
    """flash command exits non-zero when firmware download fails."""
    result = runner.invoke(app, ["flash"])
    assert result.exit_code != 0
