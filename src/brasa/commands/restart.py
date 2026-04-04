"""restart command — reboot the MicroPython device."""

import typer

from brasa.cli import app
from brasa.core.device import reset
from brasa.core.lock import port_lock
from brasa.core.output import success
from brasa.core.port import detect_port


@app.command()
def restart(ctx: typer.Context) -> None:
    """Reboot the MicroPython device."""
    port = (ctx.obj.get("port") if ctx.obj else None) or detect_port()
    with port_lock(port, "restart"):
        reset(port)
        success("device restarted")
