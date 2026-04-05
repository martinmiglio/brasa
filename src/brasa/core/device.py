"""Thin helpers for mpremote operations and hardware reset via DTR toggle."""

import subprocess
import time

import serial as pyserial

from brasa.core.output import warn


def mpremote_run(
    port: str, *args: str, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run an mpremote command connected to *port*.

    If *capture* is True, capture stdout/stderr and return the result.
    Otherwise, inherit stdio (for interactive commands like repl).
    Raises ``subprocess.CalledProcessError`` on non-zero exit.
    """
    cmd = ["mpremote", "connect", port, *args]
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True, check=True)
    return subprocess.run(cmd, text=True, check=True)


def repl(port: str) -> None:
    """Open an interactive REPL on *port*."""
    mpremote_run(port, "repl")


def reset(port: str) -> None:
    """Send a soft-reset to the device on *port*."""
    mpremote_run(port, "reset")


def exec_expr(port: str, expr: str) -> str:
    """Execute *expr* on the device and return its stdout."""
    result = mpremote_run(port, "exec", expr, capture=True)
    return result.stdout


def fs_cp(port: str, src: str, dst: str) -> None:
    """Copy *src* to *dst* via mpremote fs cp."""
    mpremote_run(port, "fs", "cp", src, dst)


def fs_cat(port: str, path: str) -> str:
    """Read the contents of *path* on the device and return them."""
    result = mpremote_run(port, "fs", "cat", path, capture=True)
    return result.stdout


def fs_ls(port: str, path: str = "/") -> str:
    """List files at *path* on the device and return the listing."""
    result = mpremote_run(port, "fs", "ls", path, capture=True)
    return result.stdout


_PLATFORM_TO_BOARD: dict[str, str] = {
    "esp8266": "ESP8266_GENERIC",
    "esp32": "ESP32_GENERIC",
    "rp2": "RPI_PICO",
}


def detect_board(port: str) -> str | None:
    """Query sys.platform on a connected device and map to a board identifier.

    Returns ``None`` if the device is not reachable or the platform is unknown.
    """
    try:
        platform = exec_expr(port, "import sys; print(sys.platform)").strip()
        return _PLATFORM_TO_BOARD.get(platform)
    except (subprocess.CalledProcessError, OSError):
        return None


def device_firmware_info(port: str) -> dict[str, str]:
    """Query the device for platform and firmware version.

    Returns a dict with ``platform``, ``board``, and ``version`` keys.
    """
    raw = exec_expr(
        port,
        "import sys; print(sys.platform); v=sys.implementation.version; print(f'{v[0]}.{v[1]}.{v[2]}')",
    ).strip()
    lines = raw.splitlines()
    platform = lines[0] if lines else ""
    version = lines[1] if len(lines) > 1 else ""
    board = _PLATFORM_TO_BOARD.get(platform, platform)
    return {"platform": platform, "board": board, "version": version}


def dtr_reset(port: str) -> None:
    """Toggle DTR to perform a hardware reset.

    Failures are logged but tolerated — the device may not support DTR reset.
    """
    try:
        with pyserial.Serial(port) as ser:
            ser.dtr = False
            time.sleep(0.1)
            ser.dtr = True
    except (pyserial.SerialException, OSError) as exc:
        warn(f"DTR reset failed on {port}: {exc}")
