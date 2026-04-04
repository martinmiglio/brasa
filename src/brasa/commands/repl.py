"""repl command — open an interactive REPL on the device."""

import typer

from brasa.cli import app
from brasa.core.device import repl as device_repl
from brasa.core.lock import port_lock
from brasa.core.port import detect_port


@app.command()
def repl(ctx: typer.Context) -> None:
    """Open an interactive REPL on the device."""
    port = (ctx.obj.get("port") if ctx.obj else None) or detect_port()
    with port_lock(port, "repl"):
        device_repl(port)
