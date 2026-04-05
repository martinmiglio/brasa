"""dev command — deploy, watch for changes, and stream serial output."""

import io
import os
import subprocess
import sys
import time

import typer
import watchfiles

from brasa.core.config import BrasaConfig, require_config
from brasa.core.deploy import deploy
from brasa.core.device import dtr_reset
from brasa.core.lock import ENV_PORT_LOCKED, resolved_port_lock
from brasa.core.output import error, status, success, warn
from brasa.core.serial import SerialReader

app = typer.Typer()

_SERIAL_RELEASE_DELAY = 1.2  # seconds for serial port to release before redeploy
_DEPLOY_RETRY_DELAY = 10  # seconds between failed deploy retries
_RESET_SETTLE_DELAY = 1  # seconds after device reset before resuming serial


@app.command()
def dev(ctx: typer.Context) -> None:
    """Deploy, watch for changes, and stream serial output."""
    cfg = require_config()
    with resolved_port_lock(
        ctx.obj.get("port"), "dev", patterns=cfg.port.patterns
    ) as port:
        os.environ[ENV_PORT_LOCKED] = port

        if isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout.reconfigure(line_buffering=True)

        status("dev", "initial deploy")
        deploy(port, cfg.deploy)
        dtr_reset(port)

        reader = SerialReader(port, baud=cfg.serial.baud_rate, filter_repl=True)
        reader.start_background()

        try:
            _watch_loop(port, cfg, reader)
        except KeyboardInterrupt:
            reader.stop()
            success("dev session ended")


def _watch_loop(port: str, cfg: BrasaConfig, reader: SerialReader) -> None:
    """Watch source files and redeploy on changes."""
    for _changes in watchfiles.watch(
        cfg.deploy.src,
        cfg.deploy.env_file,
        watch_filter=lambda change, path: path.endswith((".py", ".env")),
    ):
        status("dev", "changes detected, redeploying...")
        reader.pause()
        time.sleep(_SERIAL_RELEASE_DELAY)

        deployed = False
        for attempt in range(3):
            try:
                deploy(port, cfg.deploy)
                deployed = True
                break
            except (subprocess.CalledProcessError, OSError):
                if attempt < 2:
                    warn(
                        f"deploy failed, retrying in {_DEPLOY_RETRY_DELAY}s (attempt {attempt + 1}/3)"
                    )
                    time.sleep(_DEPLOY_RETRY_DELAY)

        if deployed:
            dtr_reset(port)
            time.sleep(_RESET_SETTLE_DELAY)
            status("dev", "redeploy complete")
        else:
            error("deploy failed after 3 attempts")

        reader.resume()
