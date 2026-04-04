"""Tests for brasa.commands.deploy — deploy command wiring."""

from contextlib import nullcontext
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from brasa.cli import app
from brasa.core.config import BrasaConfig

runner = CliRunner()


@patch("brasa.commands.deploy.success")
@patch("brasa.commands.deploy.dtr_reset")
@patch("brasa.commands.deploy.deploy_to_device")
@patch("brasa.commands.deploy.port_lock", return_value=nullcontext())
@patch("brasa.commands.deploy.resolve_port", return_value="/dev/cu.test")
@patch("brasa.commands.deploy.require_config", return_value=BrasaConfig())
def test_deploy_command(
    mock_config: MagicMock,
    mock_detect: MagicMock,
    mock_lock: MagicMock,
    mock_deploy: MagicMock,
    mock_reset: MagicMock,
    mock_success: MagicMock,
) -> None:
    """deploy command wires config, lock, deploy, and reset together."""
    result = runner.invoke(app, ["deploy"])
    assert result.exit_code == 0
    mock_config.assert_called_once()
    mock_deploy.assert_called_once_with("/dev/cu.test", BrasaConfig().deploy)
    mock_reset.assert_called_once_with("/dev/cu.test")
    mock_success.assert_called_once()


@patch("brasa.commands.deploy.success")
@patch("brasa.commands.deploy.dtr_reset")
@patch("brasa.commands.deploy.deploy_to_device")
@patch("brasa.commands.deploy.port_lock", return_value=nullcontext())
@patch("brasa.commands.deploy.require_config", return_value=BrasaConfig())
def test_deploy_with_port_override(
    mock_config: MagicMock,
    mock_lock: MagicMock,
    mock_deploy: MagicMock,
    mock_reset: MagicMock,
    mock_success: MagicMock,
) -> None:
    """deploy command uses --port override when provided."""
    result = runner.invoke(app, ["--port", "/dev/cu.manual", "deploy"])
    assert result.exit_code == 0
    mock_deploy.assert_called_once_with("/dev/cu.manual", BrasaConfig().deploy)
    mock_reset.assert_called_once_with("/dev/cu.manual")
