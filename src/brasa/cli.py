from importlib.metadata import version

import typer

app = typer.Typer(
    name="brasa",
    help="MicroPython developer tools — flash, deploy, watch, monitor.",
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
        False, "--version", "-V", callback=_version_callback, is_eager=True
    ),
    port: str | None = typer.Option(
        None, "--port", "-p", help="Serial port (auto-detected if omitted)"
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["port"] = port


# Register commands — imported after `app` is defined to avoid circular imports.
from brasa.commands import detect, exec, repl, restart, serial  # noqa: E402, F811

# Keep references so linters don't flag unused imports.
__all__ = ["detect", "exec", "repl", "restart", "serial"]


def main() -> None:
    app()
