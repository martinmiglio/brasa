"""detect command — print the auto-detected (or overridden) serial port."""

import typer

from brasa.core.output import print_stdout
from brasa.core.port import resolve_port

app = typer.Typer()


@app.command()
def detect(ctx: typer.Context) -> None:
    """Detect the serial port of a connected MicroPython device."""
    print_stdout(resolve_port(ctx.obj.get("port")))
