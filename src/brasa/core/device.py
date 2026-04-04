"""Thin helpers for mpremote operations and hardware reset via DTR toggle."""

import subprocess
import time

import serial

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
    return subprocess.run(cmd, check=True)


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


def dtr_reset(port: str) -> None:
    """Toggle DTR to perform a hardware reset.

    Failures are logged but tolerated — the device may not support DTR reset.
    """
    try:
        ser = serial.Serial(port)
        ser.dtr = False
        time.sleep(0.1)
        ser.dtr = True
        ser.close()
    except Exception as exc:  # noqa: BLE001
        warn(f"DTR reset failed on {port}: {exc}")
