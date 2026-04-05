"""Tests for the flash CLI command."""

from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from brasa.cli import app
from brasa.core.config import BrasaConfig, FirmwareConfig

runner = CliRunner()


# ── flash command wiring ────────────────────────────────────────────────────


@patch("brasa.commands.flash.resolve_port", return_value="/dev/cu.test")
@patch("brasa.commands.flash.port_lock", return_value=nullcontext())
@patch("brasa.commands.flash.flash_firmware")
@patch("brasa.commands.flash.download_firmware", return_value=Path("firmware/test.bin"))
@patch(
    "brasa.commands.flash.require_config",
    return_value=BrasaConfig(
        firmware=FirmwareConfig(
            board="ESP32_GENERIC", variant="", version="1.27.0", date="20251209"
        )
    ),
)
def test_flash_command(
    mock_require: MagicMock,
    mock_download: MagicMock,
    mock_flash: MagicMock,
    mock_lock: MagicMock,
    mock_detect: MagicMock,
) -> None:
    result = runner.invoke(app, ["flash"])
    assert result.exit_code == 0
    mock_require.assert_called_once()
    mock_download.assert_called_once()
    mock_flash.assert_called_once_with("/dev/cu.test", Path("firmware/test.bin"))


# ── flash shows deprecation warning ────────────────────────────────────────


@patch("brasa.commands.flash.resolve_port", return_value="/dev/cu.test")
@patch("brasa.commands.flash.port_lock", return_value=nullcontext())
@patch("brasa.commands.flash.flash_firmware")
@patch("brasa.commands.flash.download_firmware", return_value=Path("firmware/test.bin"))
@patch(
    "brasa.commands.flash.require_config",
    return_value=BrasaConfig(
        firmware=FirmwareConfig(
            board="ESP32_GENERIC", variant="", version="1.27.0", date="20251209"
        )
    ),
)
def test_flash_shows_deprecation_warning(
    mock_require: MagicMock,
    mock_download: MagicMock,
    mock_flash: MagicMock,
    mock_lock: MagicMock,
    mock_detect: MagicMock,
) -> None:
    result = runner.invoke(app, ["flash"])
    assert result.exit_code == 0
    assert "deprecated" in result.output.lower()


# ── flash errors on missing version ─────────────────────────────────────────


@patch(
    "brasa.commands.flash.require_config",
    return_value=BrasaConfig(
        firmware=FirmwareConfig(board="ESP32_GENERIC", date="20251209")
    ),
)
def test_flash_errors_missing_version(mock_require: MagicMock) -> None:
    result = runner.invoke(app, ["flash"])
    assert result.exit_code == 1


# ── flash errors on missing date ─────────────────────────────────────────────


@patch(
    "brasa.commands.flash.require_config",
    return_value=BrasaConfig(
        firmware=FirmwareConfig(board="ESP32_GENERIC", version="1.27.0")
    ),
)
def test_flash_errors_missing_date(mock_require: MagicMock) -> None:
    result = runner.invoke(app, ["flash"])
    assert result.exit_code == 1
