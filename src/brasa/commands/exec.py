"""exec command — execute a Python expression on the device."""

import typer

from brasa.cli import app, port_override
from brasa.core.device import exec_expr
from brasa.core.lock import port_lock
from brasa.core.output import print_stdout
from brasa.core.port import resolve_port


@app.command(name="exec")
def exec_cmd(
    ctx: typer.Context,
    expression: str = typer.Argument(help="Python expression to execute on device"),
) -> None:
    """Execute a Python expression on the device."""
    port = resolve_port(port_override(ctx))
    with port_lock(port, "exec"):
        result = exec_expr(port, expression)
        if result:
            print_stdout(result)
