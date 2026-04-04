"""deploy command — compile and push project files to the device."""

import typer

from brasa.cli import app
from brasa.core.config import require_config
from brasa.core.deploy import deploy as deploy_to_device
from brasa.core.device import dtr_reset
from brasa.core.lock import port_lock
from brasa.core.output import success
from brasa.core.port import detect_port


@app.command()
def deploy(ctx: typer.Context) -> None:
    """Compile and push project files to the device."""
    cfg = require_config()
    port = (ctx.obj.get("port") if ctx.obj else None) or detect_port()
    with port_lock(port, "deploy"):
        deploy_to_device(port, cfg.deploy)
        dtr_reset(port)
        success("deploy complete")
