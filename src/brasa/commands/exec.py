"""exec command — execute a Python expression on the device."""

import typer

from brasa.cli import app
from brasa.core.device import exec_expr
from brasa.core.lock import port_lock
from brasa.core.output import print_stdout
from brasa.core.port import detect_port


@app.command(name="exec")
def exec_cmd(
    ctx: typer.Context,
    expression: str = typer.Argument(help="Python expression to execute on device"),
) -> None:
    """Execute a Python expression on the device."""
    port = (ctx.obj.get("port") if ctx.obj else None) or detect_port()
    with port_lock(port, "exec"):
        result = exec_expr(port, expression)
        if result:
            print_stdout(result)
