"""repl command — open an interactive REPL on the device."""

import typer

from brasa.cli import app, port_override
from brasa.core.device import repl as device_repl
from brasa.core.lock import port_lock
from brasa.core.port import resolve_port


@app.command()
def repl(ctx: typer.Context) -> None:
    """Open an interactive REPL on the device."""
    port = resolve_port(port_override(ctx))
    with port_lock(port, "repl"):
        device_repl(port)
