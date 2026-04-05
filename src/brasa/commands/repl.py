"""repl command — open an interactive REPL on the device."""

import typer

from brasa.core.device import repl as device_repl
from brasa.core.lock import resolved_port_lock

app = typer.Typer()


@app.command()
def repl(ctx: typer.Context) -> None:
    """Open an interactive REPL on the device."""
    with resolved_port_lock(ctx.obj.get("port"), "repl") as port:
        device_repl(port)
