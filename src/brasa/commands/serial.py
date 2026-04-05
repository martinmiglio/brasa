"""serial command — monitor serial output from a MicroPython device."""

import typer

from brasa.core.lock import resolved_port_lock
from brasa.core.serial import SerialReader

app = typer.Typer()


@app.command()
def serial(
    ctx: typer.Context,
    baud: int = typer.Option(115200, "--baud", "-b", help="Baud rate"),
) -> None:
    """Monitor serial output from a MicroPython device."""
    with resolved_port_lock(ctx.obj.get("port"), "serial") as port:
        reader = SerialReader(port, baud=baud)
        reader.run_blocking()
