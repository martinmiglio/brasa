"""dev command — deploy, watch for changes, and stream serial output."""

import io
import os
import sys
import time

import typer
import watchfiles

from brasa.cli import app
from brasa.core.config import BrasaConfig, require_config
from brasa.core.deploy import deploy
from brasa.core.device import dtr_reset
from brasa.core.lock import port_lock
from brasa.core.output import error, status, success, warn
from brasa.core.port import detect_port
from brasa.core.serial import SerialReader


@app.command()
def dev(ctx: typer.Context) -> None:
    """Deploy, watch for changes, and stream serial output."""
    cfg = require_config()
    port = (ctx.obj.get("port") if ctx.obj else None) or detect_port(cfg.port.patterns)

    with port_lock(port, "dev"):
        os.environ["BRASA_PORT_LOCKED"] = port

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
        time.sleep(1.2)

        deployed = False
        for attempt in range(3):
            try:
                deploy(port, cfg.deploy)
                deployed = True
                break
            except Exception:
                if attempt < 2:
                    warn(f"deploy failed, retrying in 10s (attempt {attempt + 1}/3)")
                    time.sleep(10)

        if deployed:
            dtr_reset(port)
            time.sleep(1)
            status("dev", "redeploy complete")
        else:
            error("deploy failed after 3 attempts")

        reader.resume()
