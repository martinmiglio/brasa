"""exec command — execute a Python expression on the device."""

import typer

from brasa.core.device import exec_expr
from brasa.core.lock import resolved_port_lock
from brasa.core.output import print_stdout

app = typer.Typer()


@app.command(name="exec")
def exec_cmd(
    ctx: typer.Context,
    expression: str = typer.Argument(help="Python expression to execute on device"),
) -> None:
    """Execute a Python expression on the device."""
    with resolved_port_lock(ctx.obj.get("port"), "exec") as port:
        result = exec_expr(port, expression)
        if result:
            print_stdout(result)
