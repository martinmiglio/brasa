"""restart command — reboot the MicroPython device."""

import typer

from brasa.core.device import reset
from brasa.core.lock import resolved_port_lock
from brasa.core.output import success

app = typer.Typer()


@app.command()
def restart(ctx: typer.Context) -> None:
    """Reboot the MicroPython device."""
    with resolved_port_lock(ctx.obj.get("port"), "restart") as port:
        reset(port)
        success("device restarted")
