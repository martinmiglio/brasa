"""serial command — monitor serial output from a MicroPython device."""

import typer

from brasa.cli import app
from brasa.core.lock import port_lock
from brasa.core.port import detect_port
from brasa.core.serial import SerialReader


@app.command()
def serial(
    ctx: typer.Context,
    baud: int = typer.Option(115200, "--baud", "-b", help="Baud rate"),
) -> None:
    """Monitor serial output from a MicroPython device."""
    port = (ctx.obj.get("port") if ctx.obj else None) or detect_port()
    with port_lock(port, "serial"):
        reader = SerialReader(port, baud=baud)
        reader.run_blocking()
