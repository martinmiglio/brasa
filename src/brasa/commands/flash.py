"""flash command — download and flash MicroPython firmware to a device."""

import typer

from brasa.core import output
from brasa.core.config import require_config
from brasa.core.firmware import download_firmware, flash_firmware
from brasa.core.lock import port_lock
from brasa.core.output import success
from brasa.core.port import resolve_port

app = typer.Typer()


@app.command(deprecated=True)
def flash(ctx: typer.Context) -> None:
    """Download and flash MicroPython firmware. Use 'brasa firmware install --from-config' instead."""
    output.warn(
        "'brasa flash' is deprecated — use 'brasa firmware install --from-config'"
    )
    cfg = require_config()

    if not cfg.firmware.version:
        output.error("firmware.version is required in config")
        raise SystemExit(1)
    if not cfg.firmware.date:
        output.error("firmware.date is required in config")
        raise SystemExit(1)

    port = resolve_port(ctx.obj.get("port"))
    firmware_path = download_firmware(cfg.firmware)
    with port_lock(port, "flash"):
        flash_firmware(port, firmware_path)
        success("firmware flashed")
