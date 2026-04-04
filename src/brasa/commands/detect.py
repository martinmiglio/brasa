"""detect command — print the auto-detected (or overridden) serial port."""

import typer

from brasa.cli import app
from brasa.core.output import print_stdout
from brasa.core.port import detect_port


@app.command()
def detect(ctx: typer.Context) -> None:
    """Detect the serial port of a connected MicroPython device."""
    port = ctx.obj.get("port") if ctx.obj else None
    if port:
        print_stdout(port)
    else:
        print_stdout(detect_port())
