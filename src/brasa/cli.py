from importlib.metadata import version

import typer

app = typer.Typer(
    name="brasa",
    help="MicroPython developer tools — flash, deploy, watch, monitor.",
    no_args_is_help=True,
)


def port_override(ctx: typer.Context) -> str | None:
    """Extract the ``--port`` override from the CLI context."""
    return ctx.obj.get("port") if ctx.obj else None


def _version_callback(value: bool) -> None:
    if value:
        print(f"brasa {version('brasa')}")
        raise typer.Exit()


@app.callback()
def _main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True
    ),
    port: str | None = typer.Option(
        None, "--port", "-p", help="Serial port (auto-detected if omitted)"
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["port"] = port


# Register commands — imported after `app` is defined to avoid circular imports.
from brasa.commands import (  # noqa: E402, F811
    deploy,
    detect,
    dev,
    diff,
    exec,
    flash,
    repl,
    restart,
    serial,
)

# Keep references so linters don't flag unused imports.
__all__ = [
    "deploy",
    "detect",
    "dev",
    "diff",
    "exec",
    "flash",
    "repl",
    "restart",
    "serial",
]


def main() -> None:
    app()
