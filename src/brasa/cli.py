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
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True
    ),
) -> None:
    pass


def main() -> None:
    app()
