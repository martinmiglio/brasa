"""Tests for the firmware CLI sub-app commands."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from brasa.cli import app
from brasa.core.config import BrasaConfig, FirmwareConfig
from brasa.core.firmware_index import BoardIndex, BoardInfo, FirmwareEntry
from tests.conftest import fake_port_lock

runner = CliRunner()

_ENTRIES = (
    FirmwareEntry("ESP32_GENERIC", "", "1.27.0", "20251209", "f1.bin", "url1", "bin"),
    FirmwareEntry("ESP32_GENERIC", "", "1.26.1", "20250911", "f2.bin", "url2", "bin"),
    FirmwareEntry(
        "ESP32_GENERIC", "SPIRAM", "1.27.0", "20251209", "f3.bin", "url3", "bin"
    ),
)
_INDEX = BoardIndex(board="ESP32_GENERIC", entries=_ENTRIES, fetched_at=time.time())

_CFG_WITH_FIRMWARE = BrasaConfig(
    firmware=FirmwareConfig(
        board="ESP32_GENERIC", variant="SPIRAM", version="1.27.0", date="20251209"
    )
)
_CFG_NO_FIRMWARE = BrasaConfig()


# ── _resolve_board ─────────────────────────────────────────────────────────


class TestResolveBoard:
    """Tests for the board resolution chain: flag → config → device → prompt."""

    @patch("brasa.commands.firmware.load_config", return_value=_CFG_WITH_FIRMWARE)
    def test_explicit_flag_takes_priority(self, mock_cfg: MagicMock) -> None:
        from brasa.commands.firmware import _resolve_board

        assert _resolve_board("RPI_PICO") == "RPI_PICO"
        mock_cfg.assert_not_called()

    @patch("brasa.commands.firmware.load_config", return_value=_CFG_WITH_FIRMWARE)
    def test_falls_back_to_config(self, mock_cfg: MagicMock) -> None:
        from brasa.commands.firmware import _resolve_board

        assert _resolve_board(None) == "ESP32_GENERIC"

    @patch("brasa.commands.firmware.load_config", return_value=_CFG_WITH_FIRMWARE)
    def test_skips_config_when_use_config_false(self, mock_cfg: MagicMock) -> None:
        from brasa.commands.firmware import _resolve_board

        # With use_config=False and no device, should fall through to interactive.
        # Mock device detection to return something so we don't hit questionary.
        with patch("brasa.commands.firmware.resolve_port", return_value="/dev/test"):
            with patch(
                "brasa.commands.firmware.detect_board",
                return_value="RPI_PICO",
            ):
                with patch(
                    "brasa.commands.firmware._is_interactive", return_value=False
                ):
                    assert _resolve_board(None, use_config=False) == "RPI_PICO"

    @patch("brasa.commands.firmware._is_interactive", return_value=False)
    @patch(
        "brasa.commands.firmware.detect_board",
        return_value="ESP8266_GENERIC",
    )
    @patch("brasa.commands.firmware.resolve_port", return_value="/dev/test")
    @patch("brasa.commands.firmware.load_config", return_value=_CFG_NO_FIRMWARE)
    def test_falls_back_to_device_detection(
        self,
        mock_cfg: MagicMock,
        mock_port: MagicMock,
        mock_detect: MagicMock,
        mock_tty: MagicMock,
    ) -> None:
        from brasa.commands.firmware import _resolve_board

        assert _resolve_board(None) == "ESP8266_GENERIC"

    @patch("brasa.commands.firmware._is_interactive", return_value=True)
    @patch("brasa.commands.firmware.detect_board", return_value=None)
    @patch("brasa.commands.firmware.resolve_port", side_effect=SystemExit(1))
    @patch("brasa.commands.firmware.load_config", return_value=_CFG_NO_FIRMWARE)
    def test_device_detection_failure_does_not_crash(
        self,
        mock_cfg: MagicMock,
        mock_port: MagicMock,
        mock_detect: MagicMock,
        mock_tty: MagicMock,
    ) -> None:
        """When device detection fails, resolution continues to interactive prompt."""
        import questionary as q_module

        from brasa.commands.firmware import _resolve_board

        boards = [BoardInfo("ESP32_GENERIC", "ESP32")]
        with patch("brasa.commands.firmware.fetch_board_list", return_value=boards):
            with patch.object(q_module, "autocomplete") as mock_autocomplete:
                mock_autocomplete.return_value.ask.return_value = "ESP32_GENERIC"
                assert _resolve_board(None) == "ESP32_GENERIC"


# ── _resolve_entry — variant/version from config ──────────────────────────


class TestResolveEntryConfigFallback:
    """Tests that variant and version are read from config when not given as flags."""

    @patch("brasa.commands.firmware.find_entry", return_value=_ENTRIES[2])
    @patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
    @patch("brasa.commands.firmware._resolve_board", return_value="ESP32_GENERIC")
    @patch("brasa.commands.firmware.load_config", return_value=_CFG_WITH_FIRMWARE)
    def test_variant_and_version_from_config(
        self,
        mock_cfg: MagicMock,
        mock_board: MagicMock,
        mock_fetch: MagicMock,
        mock_find: MagicMock,
    ) -> None:
        from brasa.commands.firmware import _resolve_entry

        result = _resolve_entry(None, None, None)
        # Should have used SPIRAM and 1.27.0 from config, not prompted
        assert result.board == "ESP32_GENERIC"
        assert result.variant == "SPIRAM"
        assert result.version == "1.27.0"

    @patch("brasa.commands.firmware.find_entry", return_value=_ENTRIES[1])
    @patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
    @patch("brasa.commands.firmware._resolve_board", return_value="ESP32_GENERIC")
    @patch("brasa.commands.firmware.load_config", return_value=_CFG_WITH_FIRMWARE)
    def test_cli_flags_override_config(
        self,
        mock_cfg: MagicMock,
        mock_board: MagicMock,
        mock_fetch: MagicMock,
        mock_find: MagicMock,
    ) -> None:
        from brasa.commands.firmware import _resolve_entry

        result = _resolve_entry(None, "", "1.26.1")
        # CLI flags override config values
        assert result.board == "ESP32_GENERIC"
        assert result.variant == ""
        assert result.version == "1.26.1"

    @patch("brasa.commands.firmware._prompt_version", return_value="1.27.0")
    @patch("brasa.commands.firmware._prompt_variant", return_value="")
    @patch("brasa.commands.firmware.find_entry", return_value=_ENTRIES[0])
    @patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
    @patch("brasa.commands.firmware._resolve_board", return_value="ESP32_GENERIC")
    @patch("brasa.commands.firmware.load_config", return_value=_CFG_NO_FIRMWARE)
    def test_no_config_falls_through_to_prompts(
        self,
        mock_cfg: MagicMock,
        mock_board: MagicMock,
        mock_fetch: MagicMock,
        mock_find: MagicMock,
        mock_variant: MagicMock,
        mock_version: MagicMock,
    ) -> None:
        from brasa.commands.firmware import _resolve_entry

        result = _resolve_entry(None, None, None)
        mock_variant.assert_called_once()
        mock_version.assert_called_once()
        assert result.board == "ESP32_GENERIC"
        assert result.variant == ""
        assert result.version == "1.27.0"

    @patch("brasa.commands.firmware._prompt_version", return_value="1.27.0")
    @patch("brasa.commands.firmware._prompt_variant", return_value="")
    @patch("brasa.commands.firmware.find_entry", return_value=_ENTRIES[0])
    @patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
    @patch("brasa.commands.firmware._resolve_board", return_value="RPI_PICO")
    @patch("brasa.commands.firmware.load_config", return_value=_CFG_WITH_FIRMWARE)
    def test_config_skipped_when_board_differs(
        self,
        mock_cfg: MagicMock,
        mock_board: MagicMock,
        mock_fetch: MagicMock,
        mock_find: MagicMock,
        mock_variant: MagicMock,
        mock_version: MagicMock,
    ) -> None:
        """Config variant/version skipped when resolved board doesn't match config board."""
        from brasa.commands.firmware import _resolve_entry

        result = _resolve_entry(None, None, None)
        mock_variant.assert_called_once()
        mock_version.assert_called_once()
        assert result.board == "ESP32_GENERIC"
        assert result.variant == ""
        assert result.version == "1.27.0"

    @patch("brasa.commands.firmware._prompt_version", return_value="1.27.0")
    @patch("brasa.commands.firmware._prompt_variant", return_value="")
    @patch("brasa.commands.firmware.find_entry", return_value=_ENTRIES[0])
    @patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
    @patch("brasa.commands.firmware._resolve_board", return_value="ESP32_GENERIC")
    @patch("brasa.commands.firmware.load_config", return_value=_CFG_WITH_FIRMWARE)
    def test_use_config_false_skips_variant_version(
        self,
        mock_cfg: MagicMock,
        mock_board: MagicMock,
        mock_fetch: MagicMock,
        mock_find: MagicMock,
        mock_variant: MagicMock,
        mock_version: MagicMock,
    ) -> None:
        """select uses use_config=False, so variant/version should prompt."""
        from brasa.commands.firmware import _resolve_entry

        result = _resolve_entry(None, None, None, use_config=False)
        mock_variant.assert_called_once()
        mock_version.assert_called_once()
        assert result.board == "ESP32_GENERIC"
        assert result.variant == ""
        assert result.version == "1.27.0"


# ── CLI command integration tests ──────────────────────────────────────────


@patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
@patch("brasa.commands.firmware._resolve_board", return_value="ESP32_GENERIC")
def test_firmware_list_positional(
    mock_resolve: MagicMock, mock_fetch: MagicMock
) -> None:
    result = runner.invoke(app, ["firmware", "list", "ESP32_GENERIC"])
    assert result.exit_code == 0
    assert "1.27.0" in result.output
    assert "1.26.1" in result.output


@patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
@patch("brasa.commands.firmware._resolve_board", return_value="ESP32_GENERIC")
def test_firmware_list_no_board_resolves(
    mock_resolve: MagicMock, mock_fetch: MagicMock
) -> None:
    result = runner.invoke(app, ["firmware", "list"])
    assert result.exit_code == 0
    mock_resolve.assert_called_once_with(None)


@patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
@patch("brasa.commands.firmware._resolve_board", return_value="ESP32_GENERIC")
def test_firmware_list_refresh(mock_resolve: MagicMock, mock_fetch: MagicMock) -> None:
    result = runner.invoke(app, ["firmware", "list", "ESP32_GENERIC", "--refresh"])
    assert result.exit_code == 0
    mock_fetch.assert_called_once_with("ESP32_GENERIC", force_refresh=True)


@patch("brasa.commands.firmware.download_entry", return_value=Path("/cache/f1.bin"))
@patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
@patch(
    "brasa.commands.firmware.require_config",
    return_value=_CFG_WITH_FIRMWARE,
)
def test_firmware_download_from_config(
    mock_config: MagicMock, mock_fetch: MagicMock, mock_dl: MagicMock
) -> None:
    result = runner.invoke(app, ["firmware", "download", "--from-config"])
    assert result.exit_code == 0
    mock_dl.assert_called_once()


@patch("brasa.commands.firmware.write_pin")
@patch("brasa.commands.firmware.install_firmware")
@patch("brasa.commands.firmware.download_entry", return_value=Path("/cache/f1.bin"))
@patch("brasa.commands.firmware.resolved_port_lock", fake_port_lock)
@patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
@patch(
    "brasa.commands.firmware.require_config",
    return_value=_CFG_WITH_FIRMWARE,
)
def test_firmware_install_from_config_saves(
    mock_config: MagicMock,
    mock_fetch: MagicMock,
    mock_dl: MagicMock,
    mock_install: MagicMock,
    mock_pin: MagicMock,
) -> None:
    result = runner.invoke(app, ["firmware", "install", "--from-config"])
    assert result.exit_code == 0
    mock_install.assert_called_once()
    mock_pin.assert_called_once_with("ESP32_GENERIC", "SPIRAM", "1.27.0", "20251209")


@patch("brasa.commands.firmware.write_pin", return_value=Path("brasa.toml"))
@patch("brasa.commands.firmware.fetch_board_index", return_value=_INDEX)
def test_firmware_select(mock_fetch: MagicMock, mock_pin: MagicMock) -> None:
    result = runner.invoke(
        app,
        [
            "firmware",
            "select",
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


@patch(
    "brasa.commands.firmware.device_firmware_info",
    return_value={
        "platform": "esp8266",
        "board": "ESP8266_GENERIC",
        "version": "1.27.0",
    },
)
@patch("brasa.commands.firmware.resolved_port_lock", fake_port_lock)
def test_firmware_show(mock_info: MagicMock) -> None:
    result = runner.invoke(app, ["firmware", "show"])
    assert result.exit_code == 0
    assert "ESP8266_GENERIC" in result.output
    assert "1.27.0" in result.output


@patch(
    "brasa.commands.firmware.device_firmware_info",
    return_value={
        "platform": "esp8266",
        "board": "ESP8266_GENERIC",
        "version": "1.27.0",
    },
)
@patch("brasa.commands.firmware.resolved_port_lock", fake_port_lock)
def test_firmware_show_json(mock_info: MagicMock) -> None:
    result = runner.invoke(app, ["firmware", "show", "--json"])
    assert result.exit_code == 0
    assert '"board": "ESP8266_GENERIC"' in result.output
    assert '"version": "1.27.0"' in result.output


def test_firmware_no_args_shows_help() -> None:
    result = runner.invoke(app, ["firmware"])
    assert "list" in result.output
    assert "download" in result.output
    assert "install" in result.output
    assert "select" in result.output
    assert "show" in result.output
