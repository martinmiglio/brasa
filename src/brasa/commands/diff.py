"""diff command — show differences between local src/ and device files."""

import typer

from brasa.cli import app, port_override
from brasa.core.config import require_config
from brasa.core.diff import diff_files, print_diff
from brasa.core.lock import port_lock
from brasa.core.port import resolve_port


@app.command()
def diff(ctx: typer.Context) -> None:
    """Show differences between local src/ and device files."""
    cfg = require_config()
    port = resolve_port(port_override(ctx))
    with port_lock(port, "diff"):
        diffs = diff_files(port, cfg.deploy)
        print_diff(diffs)
