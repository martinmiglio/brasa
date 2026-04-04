"""serial command — monitor serial output from a MicroPython device."""

import typer

from brasa.cli import app, port_override
from brasa.core.lock import port_lock
from brasa.core.port import resolve_port
from brasa.core.serial import SerialReader


@app.command()
def serial(
    ctx: typer.Context,
    baud: int = typer.Option(115200, "--baud", "-b", help="Baud rate"),
) -> None:
    """Monitor serial output from a MicroPython device."""
    port = resolve_port(port_override(ctx))
    with port_lock(port, "serial"):
        reader = SerialReader(port, baud=baud)
        reader.run_blocking()
