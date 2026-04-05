"""restart command — reboot the MicroPython device."""

import typer

from brasa.core.device import reset
from brasa.core.lock import port_lock
from brasa.core.output import success
from brasa.core.port import resolve_port

app = typer.Typer()


@app.command()
def restart(ctx: typer.Context) -> None:
    """Reboot the MicroPython device."""
    port = resolve_port(ctx.obj.get("port"))
    with port_lock(port, "restart"):
        reset(port)
        success("device restarted")
