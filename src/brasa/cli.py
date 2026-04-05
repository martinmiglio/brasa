"""brasa CLI — MicroPython developer tools."""

from importlib.metadata import version

import typer

from brasa.commands.deploy import app as deploy_app
from brasa.commands.detect import app as detect_app
from brasa.commands.dev import app as dev_app
from brasa.commands.diff import app as diff_app
from brasa.commands.exec import app as exec_app
from brasa.commands.firmware import firmware_app
from brasa.commands.repl import app as repl_app
from brasa.commands.restart import app as restart_app
from brasa.commands.serial import app as serial_app

app = typer.Typer(
    name="brasa",
    help="MicroPython developer tools — deploy, watch, monitor.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        print(f"brasa {version('brasa')}")
        raise typer.Exit()


@app.callback()
def _main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    port: str | None = typer.Option(
        None, "--port", "-p", help="Serial port (auto-detected if omitted)"
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["port"] = port


app.add_typer(deploy_app)
app.add_typer(detect_app)
app.add_typer(dev_app)
app.add_typer(diff_app)
app.add_typer(exec_app)
app.add_typer(repl_app)
app.add_typer(restart_app)
app.add_typer(serial_app)
app.add_typer(firmware_app, name="firmware")


def main() -> None:
    app()
