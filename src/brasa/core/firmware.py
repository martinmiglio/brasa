"""Firmware download and flash — fetch MicroPython binaries and write via esptool."""

import subprocess
from pathlib import Path

import httpx

from brasa.core import output
from brasa.core.config import FirmwareConfig

_BASE_URL = "https://micropython.org/resources/firmware"


def _firmware_filename(cfg: FirmwareConfig) -> str:
    """Build the firmware binary filename from config."""
    return f"{cfg.board}_{cfg.variant}-{cfg.date}-v{cfg.version}.bin"


def firmware_url(cfg: FirmwareConfig) -> str:
    """Build the MicroPython firmware download URL."""
    return f"{_BASE_URL}/{_firmware_filename(cfg)}"


def firmware_cache_path(cfg: FirmwareConfig) -> Path:
    """Return the local cache path for the firmware binary (firmware/<filename>)."""
    return Path("firmware") / _firmware_filename(cfg)


def download_firmware(cfg: FirmwareConfig) -> Path:
    """Download firmware via httpx streaming with progress. Skip if cached. Return local path."""
    path = firmware_cache_path(cfg)
    if path.exists():
        output.status("firmware", f"cached: {path}")
        return path

    url = firmware_url(cfg)
    output.status("firmware", f"downloading {url}")
    path.parent.mkdir(parents=True, exist_ok=True)

    with httpx.stream("GET", url, follow_redirects=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        downloaded = 0
        with path.open("wb") as f:
            for chunk in response.iter_bytes(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    output.status("firmware", f"downloading… {pct}%")

    output.status("firmware", f"saved to {path}")
    return path


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
