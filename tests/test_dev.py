"""Tests for the dev command — deploy, watch, redeploy loop."""

import os
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from brasa.cli import app
from brasa.core.config import BrasaConfig
from tests.conftest import fake_port_lock

runner = CliRunner()

_PORT = "/dev/cu.test"
_CFG = BrasaConfig()


@patch("brasa.commands.dev.watchfiles.watch", return_value=iter([]))
@patch("brasa.commands.dev.SerialReader")
@patch("brasa.commands.dev.dtr_reset")
@patch("brasa.commands.dev.deploy")
@patch("brasa.commands.dev.resolved_port_lock", fake_port_lock)
@patch("brasa.commands.dev.require_config", return_value=_CFG)
def test_initial_deploy_called(
    mock_cfg: MagicMock,
    mock_deploy: MagicMock,
    mock_reset: MagicMock,
    mock_reader_cls: MagicMock,
    mock_watch: MagicMock,
) -> None:
    """Dev command performs initial deploy and starts serial reader."""
    result = runner.invoke(app, ["dev"])
    assert result.exit_code == 0
    mock_deploy.assert_called_once_with(_PORT, _CFG.deploy)
    mock_reset.assert_called_once_with(_PORT)
    mock_reader_cls.return_value.start_background.assert_called_once()


@patch("brasa.commands.dev.time.sleep")
@patch(
    "brasa.commands.dev.watchfiles.watch",
    return_value=iter([({("modified", "src/app.py")},)]),
)
@patch("brasa.commands.dev.SerialReader")
@patch("brasa.commands.dev.dtr_reset")
@patch("brasa.commands.dev.deploy")
@patch("brasa.commands.dev.resolved_port_lock", fake_port_lock)
@patch("brasa.commands.dev.require_config", return_value=_CFG)
def test_file_change_triggers_redeploy(
    mock_cfg: MagicMock,
    mock_deploy: MagicMock,
    mock_reset: MagicMock,
    mock_reader_cls: MagicMock,
    mock_watch: MagicMock,
    mock_sleep: MagicMock,
) -> None:
    """File change pauses reader, redeploys, resets, resumes."""
    reader_instance = mock_reader_cls.return_value
    result = runner.invoke(app, ["dev"])
    assert result.exit_code == 0

    # Initial deploy + redeploy = 2 calls
    assert mock_deploy.call_count == 2
    reader_instance.pause.assert_called_once()
    reader_instance.resume.assert_called_once()
    # dtr_reset: initial + after redeploy
    assert mock_reset.call_count == 2


@patch("brasa.commands.dev.time.sleep")
@patch(
    "brasa.commands.dev.watchfiles.watch",
    return_value=iter([({("modified", "src/app.py")},)]),
)
@patch("brasa.commands.dev.SerialReader")
@patch("brasa.commands.dev.dtr_reset")
@patch("brasa.commands.dev.deploy")
@patch("brasa.commands.dev.resolved_port_lock", fake_port_lock)
@patch("brasa.commands.dev.require_config", return_value=_CFG)
def test_deploy_retry_logic(
    mock_cfg: MagicMock,
    mock_deploy: MagicMock,
    mock_reset: MagicMock,
    mock_reader_cls: MagicMock,
    mock_watch: MagicMock,
    mock_sleep: MagicMock,
) -> None:
    """Deploy retries up to 3 times on failure, succeeds on third."""
    # First call (initial deploy) succeeds,
    # then fail twice, succeed on third
    mock_deploy.side_effect = [
        None,
        OSError("fail"),
        OSError("fail"),
        None,
    ]
    result = runner.invoke(app, ["dev"])
    assert result.exit_code == 0
    assert mock_deploy.call_count == 4  # 1 initial + 3 retries (2 fail + 1 success)
    # dtr_reset called for initial + successful redeploy
    assert mock_reset.call_count == 2


@patch("brasa.commands.dev.error")
@patch("brasa.commands.dev.time.sleep")
@patch(
    "brasa.commands.dev.watchfiles.watch",
    return_value=iter([({("modified", "src/app.py")},)]),
)
@patch("brasa.commands.dev.SerialReader")
@patch("brasa.commands.dev.dtr_reset")
@patch("brasa.commands.dev.deploy")
@patch("brasa.commands.dev.resolved_port_lock", fake_port_lock)
@patch("brasa.commands.dev.require_config", return_value=_CFG)
def test_deploy_failure_after_retries(
    mock_cfg: MagicMock,
    mock_deploy: MagicMock,
    mock_reset: MagicMock,
    mock_reader_cls: MagicMock,
    mock_watch: MagicMock,
    mock_sleep: MagicMock,
    mock_error: MagicMock,
) -> None:
    """After 3 failed attempts, error is logged and reader resumes."""
    # Initial deploy succeeds, then all 3 retries fail
    mock_deploy.side_effect = [
        None,
        OSError("x"),
        OSError("x"),
        OSError("x"),
    ]
    result = runner.invoke(app, ["dev"])
    assert result.exit_code == 0
    mock_error.assert_called_with("deploy failed after 3 attempts")
    # dtr_reset only for initial deploy
    assert mock_reset.call_count == 1
    # Reader still resumes after failure
    mock_reader_cls.return_value.resume.assert_called_once()


@patch("brasa.commands.dev.watchfiles.watch", side_effect=KeyboardInterrupt)
@patch("brasa.commands.dev.SerialReader")
@patch("brasa.commands.dev.dtr_reset")
@patch("brasa.commands.dev.deploy")
@patch("brasa.commands.dev.resolved_port_lock", fake_port_lock)
@patch("brasa.commands.dev.require_config", return_value=_CFG)
def test_keyboard_interrupt_stops_reader(
    mock_cfg: MagicMock,
    mock_deploy: MagicMock,
    mock_reset: MagicMock,
    mock_reader_cls: MagicMock,
    mock_watch: MagicMock,
) -> None:
    """KeyboardInterrupt calls reader.stop() and exits cleanly."""
    result = runner.invoke(app, ["dev"])
    assert result.exit_code == 0
    mock_reader_cls.return_value.stop.assert_called_once()


@patch("brasa.commands.dev.watchfiles.watch", return_value=iter([]))
@patch("brasa.commands.dev.SerialReader")
@patch("brasa.commands.dev.dtr_reset")
@patch("brasa.commands.dev.deploy")
@patch("brasa.commands.dev.resolved_port_lock", fake_port_lock)
@patch("brasa.commands.dev.require_config", return_value=_CFG)
def test_port_locked_env_var_set(
    mock_cfg: MagicMock,
    mock_deploy: MagicMock,
    mock_reset: MagicMock,
    mock_reader_cls: MagicMock,
    mock_watch: MagicMock,
) -> None:
    """BRASA_PORT_LOCKED env var is set to the port during dev session."""
    captured_env: dict[str, str] = {}

    def capture_deploy(port: str, cfg: object) -> None:
        captured_env["BRASA_PORT_LOCKED"] = os.environ.get("BRASA_PORT_LOCKED", "")

    mock_deploy.side_effect = capture_deploy
    result = runner.invoke(app, ["dev"])
    assert result.exit_code == 0
    assert captured_env["BRASA_PORT_LOCKED"] == _PORT
