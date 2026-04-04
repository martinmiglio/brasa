"""Tests for brasa.core.firmware — URL building, caching, download, flash."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from brasa.core.config import FirmwareConfig
from brasa.core.firmware import (
    download_firmware,
    firmware_cache_path,
    firmware_url,
    flash_firmware,
)

# ── firmware_url ────────────────────────────────────────────────────────────


def test_firmware_url() -> None:
    cfg = FirmwareConfig(
        board="ESP32", variant="GENERIC", version="1.23.0", date="2025-01-01"
    )
    url = firmware_url(cfg)
    assert (
        url
        == "https://micropython.org/resources/firmware/ESP32_GENERIC-2025-01-01-v1.23.0.bin"
    )


# ── firmware_cache_path ─────────────────────────────────────────────────────


def test_firmware_cache_path() -> None:
    cfg = FirmwareConfig(
        board="ESP32", variant="GENERIC", version="1.23.0", date="2025-01-01"
    )
    path = firmware_cache_path(cfg)
    assert path == Path(".brasa/firmware/ESP32_GENERIC-2025-01-01-v1.23.0.bin")


# ── download_firmware — cached ──────────────────────────────────────────────


@patch("brasa.core.firmware.firmware_cache_path")
def test_download_firmware_skips_when_cached(mock_cache_path: MagicMock) -> None:
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_cache_path.return_value = mock_path

    cfg = FirmwareConfig(
        board="ESP32", variant="GENERIC", version="1.23.0", date="2025-01-01"
    )
    result = download_firmware(cfg)
    assert result is mock_path
    mock_path.exists.assert_called_once()


# ── download_firmware — not cached ──────────────────────────────────────────


@patch("brasa.core.firmware.httpx")
@patch("brasa.core.firmware.firmware_cache_path")
def test_download_firmware_downloads_when_not_cached(
    mock_cache_path: MagicMock, mock_httpx: MagicMock
) -> None:
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = False
    mock_cache_path.return_value = mock_path

    mock_response = MagicMock()
    mock_response.headers = {"content-length": "1024"}
    mock_response.iter_bytes.return_value = [b"x" * 1024]
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_httpx.stream.return_value = mock_response

    cfg = FirmwareConfig(
        board="ESP32", variant="GENERIC", version="1.23.0", date="2025-01-01"
    )
    result = download_firmware(cfg)
    assert result is mock_path
    mock_httpx.stream.assert_called_once()


# ── flash_firmware ──────────────────────────────────────────────────────────


def test_flash_firmware_calls_esptool(fp) -> None:  # type: ignore[no-untyped-def]
    """Test that flash_firmware invokes esptool with correct arguments."""
    fp.register(["esptool", "--port", "/dev/cu.test", "erase-flash"])
    fp.register(
        [
            "esptool",
            "--port",
            "/dev/cu.test",
            "--baud",
            "460800",
            "write-flash",
            "--flash-size=detect",
            "0",
            "firmware/test.bin",
        ]
    )

    flash_firmware("/dev/cu.test", Path("firmware/test.bin"))

    assert fp.call_count(["esptool", "--port", "/dev/cu.test", "erase-flash"]) == 1
    assert (
        fp.call_count(
            [
                "esptool",
                "--port",
                "/dev/cu.test",
                "--baud",
                "460800",
                "write-flash",
                "--flash-size=detect",
                "0",
                "firmware/test.bin",
            ]
        )
        == 1
    )
