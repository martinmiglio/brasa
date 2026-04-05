"""Firmware download and flash — fetch MicroPython binaries and write via esptool or UF2."""

import glob
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

from brasa.core import output
from brasa.core.config import FirmwareConfig
from brasa.core.firmware_index import FirmwareEntry, cache_dir

_BASE_URL = "https://micropython.org/resources/firmware"


def _firmware_ext(board: str) -> str:
    """Infer firmware file extension from board name."""
    upper = board.upper()
    if any(prefix in upper for prefix in ("RPI_PICO", "RP2", "ARDUINO_NANO_RP")):
        return "uf2"
    return "bin"


def _firmware_filename(cfg: FirmwareConfig) -> str:
    """Build the firmware binary filename from config."""
    ext = _firmware_ext(cfg.board)
    if cfg.variant:
        return f"{cfg.board}-{cfg.variant}-{cfg.date}-v{cfg.version}.{ext}"
    return f"{cfg.board}-{cfg.date}-v{cfg.version}.{ext}"


def firmware_url(cfg: FirmwareConfig) -> str:
    """Build the MicroPython firmware download URL."""
    return f"{_BASE_URL}/{_firmware_filename(cfg)}"


def firmware_cache_path(cfg: FirmwareConfig) -> Path:
    """Return the local cache path for the firmware binary (~/.cache/brasa/firmware/)."""
    return cache_dir() / _firmware_filename(cfg)


def _download_file(url: str, dest: Path) -> Path:
    """Download *url* to *dest* with streaming progress. Skip if already cached."""
    if dest.exists():
        output.status("firmware", f"cached: {dest}")
        return dest

    output.status("firmware", f"downloading {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    brasa_dir = path.parent.parent  # .brasa/
    gitignore = brasa_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n")

    with httpx.stream("GET", url, follow_redirects=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        downloaded = 0
        with dest.open("wb") as f:
            for chunk in response.iter_bytes(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    output.status("firmware", f"downloading… {pct}%")

    output.status("firmware", f"saved to {dest}")
    return dest


def download_firmware(cfg: FirmwareConfig) -> Path:
    """Download firmware via httpx streaming with progress. Skip if cached. Return local path."""
    return _download_file(firmware_url(cfg), firmware_cache_path(cfg))


def download_entry(entry: FirmwareEntry) -> Path:
    """Download a firmware entry to the cache. Skip if already cached. Return local path."""
    return _download_file(entry.url, cache_dir() / entry.filename)


def flash_firmware(port: str, firmware_path: Path) -> None:
    """Erase flash then write firmware via esptool subprocess."""
    output.status("flash", f"erasing flash on {port}")
    subprocess.run(["esptool", "--port", port, "erase-flash"], check=True)

    output.status("flash", f"writing {firmware_path} to {port}")
    subprocess.run(
        [
            "esptool",
            "--port",
            port,
            "--baud",
            "460800",
            "write-flash",
            "--flash-size=detect",
            "0",
            str(firmware_path),
        ],
        check=True,
    )


def _detect_uf2_mount() -> Path | None:
    """Auto-detect a mounted UF2 volume (RP2 in bootloader mode)."""
    if sys.platform == "darwin":
        patterns = ["/Volumes/RPI-*", "/Volumes/RP2*"]
    else:
        patterns = [
            "/media/*/RPI-*",
            "/media/*/RP2*",
            "/run/media/*/RPI-*",
            "/run/media/*/RP2*",
        ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return Path(matches[0])
    return None


def install_uf2(firmware_path: Path, mount_point: Path | None = None) -> None:
    """Copy a UF2 file to the RP2 mass storage device."""
    if mount_point is None:
        mount_point = _detect_uf2_mount()
    if mount_point is None:
        output.error(
            "no UF2 volume detected — put the board in bootloader mode "
            "(hold BOOTSEL while plugging in) and try again"
        )
        raise SystemExit(1)

    output.status("flash", f"copying {firmware_path.name} to {mount_point}")
    shutil.copy2(firmware_path, mount_point / firmware_path.name)
    output.success("firmware copied — board will reboot automatically")


def install_firmware(
    firmware_path: Path, *, port: str | None = None, platform: str = "esp"
) -> None:
    """Install firmware using the appropriate method for the platform."""
    if platform == "uf2":
        install_uf2(firmware_path)
    elif port:
        flash_firmware(port, firmware_path)
    else:
        output.error("serial port required for ESP flashing")
        raise SystemExit(1)


def platform_for_board(board: str) -> str:
    """Infer the flash platform from the board name."""
    if _firmware_ext(board) == "uf2":
        return "uf2"
    return "esp"
