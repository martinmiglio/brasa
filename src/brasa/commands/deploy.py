"""deploy command — compile and push project files to the device."""

import typer

from brasa.core.config import require_config
from brasa.core.deploy import deploy as deploy_to_device
from brasa.core.device import dtr_reset
from brasa.core.lock import resolved_port_lock
from brasa.core.output import success

app = typer.Typer()


@app.command()
def deploy(ctx: typer.Context) -> None:
    """Compile and push project files to the device."""
    cfg = require_config()
    with resolved_port_lock(ctx.obj.get("port"), "deploy") as port:
        deploy_to_device(port, cfg.deploy)
        dtr_reset(port)
        success("deploy complete")
