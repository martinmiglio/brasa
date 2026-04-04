"""Tests for the dev command — deploy, watch, redeploy loop."""

import os
from contextlib import nullcontext
from unittest.mock import patch

from typer.testing import CliRunner

from brasa.cli import app
from brasa.core.config import BrasaConfig

runner = CliRunner()

_PORT = "/dev/cu.test"
_CFG = BrasaConfig()


def _make_patches() -> dict[str, object]:
    """Return a dict of common patches for the dev command."""
    return {
        "require_config": patch("brasa.commands.dev.require_config", return_value=_CFG),
        "detect_port": patch("brasa.commands.dev.detect_port", return_value=_PORT),
        "port_lock": patch("brasa.commands.dev.port_lock", return_value=nullcontext()),
        "deploy": patch("brasa.commands.dev.deploy"),
        "dtr_reset": patch("brasa.commands.dev.dtr_reset"),
        "SerialReader": patch("brasa.commands.dev.SerialReader"),
        "watchfiles_watch": patch("brasa.commands.dev.watchfiles.watch"),
    }


def test_initial_deploy_called() -> None:
    """Dev command performs initial deploy and starts serial reader."""
    patches = _make_patches()
    # watchfiles.watch yields nothing then stops
    patches["watchfiles_watch"] = patch(
        "brasa.commands.dev.watchfiles.watch", return_value=iter([])
    )
    with (
        patches["require_config"],
        patches["detect_port"],
        patches["port_lock"],
        patches["deploy"] as mock_deploy,
        patches["dtr_reset"] as mock_reset,
        patches["SerialReader"] as mock_reader_cls,
        patches["watchfiles_watch"],
    ):
        result = runner.invoke(app, ["dev"])
        assert result.exit_code == 0
        mock_deploy.assert_called_once_with(_PORT, _CFG.deploy)
        mock_reset.assert_called_once_with(_PORT)
        mock_reader_cls.return_value.start_background.assert_called_once()


def test_file_change_triggers_redeploy() -> None:
    """File change pauses reader, redeploys, resets, resumes."""
    patches = _make_patches()
    changes = [({("modified", "src/app.py")},)]
    patches["watchfiles_watch"] = patch(
        "brasa.commands.dev.watchfiles.watch", return_value=iter(changes)
    )
    # Patch time.sleep to skip delays
    with (
        patches["require_config"],
        patches["detect_port"],
        patches["port_lock"],
        patches["deploy"] as mock_deploy,
        patches["dtr_reset"] as mock_reset,
        patches["SerialReader"] as mock_reader_cls,
        patches["watchfiles_watch"],
        patch("brasa.commands.dev.time.sleep"),
    ):
        reader_instance = mock_reader_cls.return_value
        result = runner.invoke(app, ["dev"])
        assert result.exit_code == 0

        # Initial deploy + redeploy = 2 calls
        assert mock_deploy.call_count == 2
        reader_instance.pause.assert_called_once()
        reader_instance.resume.assert_called_once()
        # dtr_reset: initial + after redeploy
        assert mock_reset.call_count == 2


def test_deploy_retry_logic() -> None:
    """Deploy retries up to 3 times on failure, succeeds on third."""
    patches = _make_patches()
    changes = [({("modified", "src/app.py")},)]
    patches["watchfiles_watch"] = patch(
        "brasa.commands.dev.watchfiles.watch", return_value=iter(changes)
    )
    with (
        patches["require_config"],
        patches["detect_port"],
        patches["port_lock"],
        patches["deploy"] as mock_deploy,
        patches["dtr_reset"] as mock_reset,
        patches["SerialReader"],
        patches["watchfiles_watch"],
        patch("brasa.commands.dev.time.sleep"),
    ):
        # First call (initial deploy) succeeds,
        # then fail twice, succeed on third
        mock_deploy.side_effect = [
            None,
            RuntimeError("fail"),
            RuntimeError("fail"),
            None,
        ]
        result = runner.invoke(app, ["dev"])
        assert result.exit_code == 0
        assert mock_deploy.call_count == 4  # 1 initial + 3 retries (2 fail + 1 success)
        # dtr_reset called for initial + successful redeploy
        assert mock_reset.call_count == 2


def test_deploy_failure_after_retries() -> None:
    """After 3 failed attempts, error is logged and reader resumes."""
    patches = _make_patches()
    changes = [({("modified", "src/app.py")},)]
    patches["watchfiles_watch"] = patch(
        "brasa.commands.dev.watchfiles.watch", return_value=iter(changes)
    )
    with (
        patches["require_config"],
        patches["detect_port"],
        patches["port_lock"],
        patches["deploy"] as mock_deploy,
        patches["dtr_reset"] as mock_reset,
        patches["SerialReader"] as mock_reader_cls,
        patches["watchfiles_watch"],
        patch("brasa.commands.dev.time.sleep"),
        patch("brasa.commands.dev.error") as mock_error,
    ):
        # Initial deploy succeeds, then all 3 retries fail
        mock_deploy.side_effect = [
            None,
            RuntimeError("x"),
            RuntimeError("x"),
            RuntimeError("x"),
        ]
        result = runner.invoke(app, ["dev"])
        assert result.exit_code == 0
        mock_error.assert_called_with("deploy failed after 3 attempts")
        # dtr_reset only for initial deploy
        assert mock_reset.call_count == 1
        # Reader still resumes after failure
        mock_reader_cls.return_value.resume.assert_called_once()


def test_keyboard_interrupt_stops_reader() -> None:
    """KeyboardInterrupt calls reader.stop() and exits cleanly."""
    patches = _make_patches()
    patches["watchfiles_watch"] = patch(
        "brasa.commands.dev.watchfiles.watch", side_effect=KeyboardInterrupt
    )
    with (
        patches["require_config"],
        patches["detect_port"],
        patches["port_lock"],
        patches["deploy"],
        patches["dtr_reset"],
        patches["SerialReader"] as mock_reader_cls,
        patches["watchfiles_watch"],
    ):
        result = runner.invoke(app, ["dev"])
        assert result.exit_code == 0
        mock_reader_cls.return_value.stop.assert_called_once()


def test_port_locked_env_var_set() -> None:
    """BRASA_PORT_LOCKED env var is set to the port during dev session."""
    patches = _make_patches()
    captured_env: dict[str, str] = {}

    def capture_deploy(port: str, cfg: object) -> None:
        captured_env["BRASA_PORT_LOCKED"] = os.environ.get("BRASA_PORT_LOCKED", "")

    patches["watchfiles_watch"] = patch(
        "brasa.commands.dev.watchfiles.watch", return_value=iter([])
    )
    with (
        patches["require_config"],
        patches["detect_port"],
        patches["port_lock"],
        patches["deploy"] as mock_deploy,
        patches["dtr_reset"],
        patches["SerialReader"],
        patches["watchfiles_watch"],
    ):
        mock_deploy.side_effect = capture_deploy
        result = runner.invoke(app, ["dev"])
        assert result.exit_code == 0
        assert captured_env["BRASA_PORT_LOCKED"] == _PORT
