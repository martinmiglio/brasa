"""diff command — show differences between local src/ and device files."""

import typer

from brasa.core.config import require_config
from brasa.core.diff import diff_files, print_diff
from brasa.core.lock import resolved_port_lock

app = typer.Typer()


@app.command()
def diff(ctx: typer.Context) -> None:
    """Show differences between local src/ and device files."""
    cfg = require_config()
    with resolved_port_lock(ctx.obj.get("port"), "diff") as port:
        diffs = diff_files(port, cfg.deploy)
        print_diff(diffs)
