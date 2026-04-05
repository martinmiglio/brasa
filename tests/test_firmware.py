"""Tests for brasa.core.firmware — URL building, caching, download, flash."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from brasa.core.config import FirmwareConfig
from brasa.core.firmware import (
    _firmware_ext,
    download_firmware,
    firmware_cache_path,
    firmware_url,
    flash_firmware,
    install_uf2,
    platform_for_board,
)

# ── _firmware_ext ──────────────────────────────────────────────────────────


def test_firmware_ext_esp() -> None:
    assert _firmware_ext("ESP32_GENERIC") == "bin"
    assert _firmware_ext("ESP8266_GENERIC") == "bin"


def test_firmware_ext_rp2() -> None:
    assert _firmware_ext("RPI_PICO") == "uf2"
    assert _firmware_ext("RPI_PICO2") == "uf2"


# ── platform_for_board ─────────────────────────────────────────────────────


def test_platform_for_board() -> None:
    assert platform_for_board("ESP32_GENERIC") == "esp"
    assert platform_for_board("RPI_PICO") == "uf2"


# ── firmware_url ────────────────────────────────────────────────────────────


def test_firmware_url_esp() -> None:
    cfg = FirmwareConfig(
        board="ESP32_GENERIC", variant="SPIRAM", version="1.27.0", date="20251209"
    )
    url = firmware_url(cfg)
    assert (
        url
        == "https://micropython.org/resources/firmware/ESP32_GENERIC-SPIRAM-20251209-v1.27.0.bin"
    )


def test_firmware_url_no_variant() -> None:
    cfg = FirmwareConfig(
        board="ESP32_GENERIC", variant="", version="1.27.0", date="20251209"
    )
    url = firmware_url(cfg)
    assert (
        url
        == "https://micropython.org/resources/firmware/ESP32_GENERIC-20251209-v1.27.0.bin"
    )


def test_firmware_url_uf2() -> None:
    cfg = FirmwareConfig(
        board="RPI_PICO", variant="", version="1.27.0", date="20251209"
    )
    url = firmware_url(cfg)
    assert url.endswith(".uf2")


# ── firmware_cache_path ─────────────────────────────────────────────────────


@patch("brasa.core.firmware.cache_dir", return_value=Path("/tmp/test-cache"))
def test_firmware_cache_path(mock_cache: MagicMock) -> None:
    cfg = FirmwareConfig(
        board="ESP32_GENERIC", variant="", version="1.27.0", date="20251209"
    )
    path = firmware_cache_path(cfg)
    assert path == Path("/tmp/test-cache/ESP32_GENERIC-20251209-v1.27.0.bin")


# ── download_firmware — cached ──────────────────────────────────────────────


@patch("brasa.core.firmware.firmware_cache_path")
def test_download_firmware_skips_when_cached(mock_cache_path: MagicMock) -> None:
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_cache_path.return_value = mock_path

    cfg = FirmwareConfig(
        board="ESP32_GENERIC", variant="", version="1.27.0", date="20251209"
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
        board="ESP32_GENERIC", variant="", version="1.27.0", date="20251209"
    )
    result = download_firmware(cfg)
    assert result is mock_path
    mock_httpx.stream.assert_called_once()


# ── flash_firmware ──────────────────────────────────────────────────────────


def test_flash_firmware_calls_esptool(fp) -> None:  # type: ignore[no-untyped-def]
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


# ── install_uf2 ─────────────────────────────────────────────────────────────


@patch("brasa.core.firmware.shutil.copy2")
def test_install_uf2_copies_file(mock_copy: MagicMock, tmp_path: Path) -> None:
    mount = tmp_path / "RPI-RP2"
    mount.mkdir()
    fw = tmp_path / "test.uf2"
    fw.write_bytes(b"UF2 data")

    install_uf2(fw, mount_point=mount)
    mock_copy.assert_called_once_with(fw, mount / "test.uf2")


@patch("brasa.core.firmware._detect_uf2_mount", return_value=None)
def test_install_uf2_errors_no_mount(mock_detect: MagicMock) -> None:
    import pytest

    with pytest.raises(SystemExit):
        install_uf2(Path("test.uf2"))
