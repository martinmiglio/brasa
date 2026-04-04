"""flash command — download and flash MicroPython firmware to a device."""

import typer

from brasa.cli import app
from brasa.core import output
from brasa.core.config import require_config
from brasa.core.firmware import download_firmware, flash_firmware
from brasa.core.lock import port_lock
from brasa.core.output import success
from brasa.core.port import detect_port


@app.command()
def flash(ctx: typer.Context) -> None:
    """Download and flash MicroPython firmware to the device."""
    cfg = require_config()

    if not cfg.firmware.version:
        output.error("firmware.version is required in config")
        raise SystemExit(1)
    if not cfg.firmware.date:
        output.error("firmware.date is required in config")
        raise SystemExit(1)

    firmware_path = download_firmware(cfg.firmware)
    port = (ctx.obj.get("port") if ctx.obj else None) or detect_port()
    with port_lock(port, "flash"):
        flash_firmware(port, firmware_path)
        success("firmware flashed")
