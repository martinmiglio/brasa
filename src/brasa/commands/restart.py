"""restart command — reboot the MicroPython device."""

import typer

from brasa.cli import app, port_override
from brasa.core.device import reset
from brasa.core.lock import port_lock
from brasa.core.output import success
from brasa.core.port import resolve_port


@app.command()
def restart(ctx: typer.Context) -> None:
    """Reboot the MicroPython device."""
    port = resolve_port(port_override(ctx))
    with port_lock(port, "restart"):
        reset(port)
        success("device restarted")
