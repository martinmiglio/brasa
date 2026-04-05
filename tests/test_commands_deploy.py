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
    mock_resolve: MagicMock,
    mock_lock: MagicMock,
    mock_deploy: MagicMock,
    mock_reset: MagicMock,
    mock_success: MagicMock,
) -> None:
    """deploy command exits 0 on success."""
    result = runner.invoke(app, ["deploy"])
    assert result.exit_code == 0


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
    """deploy command exits 0 when --port override is provided."""
    result = runner.invoke(app, ["--port", "/dev/cu.manual", "deploy"])
    assert result.exit_code == 0


@patch("brasa.commands.deploy.dtr_reset")
@patch(
    "brasa.commands.deploy.deploy_to_device",
    side_effect=SystemExit(1),
)
@patch("brasa.commands.deploy.port_lock", return_value=nullcontext())
@patch("brasa.commands.deploy.resolve_port", return_value="/dev/cu.test")
@patch("brasa.commands.deploy.require_config", return_value=BrasaConfig())
def test_deploy_command_failure(
    mock_config: MagicMock,
    mock_resolve: MagicMock,
    mock_lock: MagicMock,
    mock_deploy: MagicMock,
    mock_reset: MagicMock,
) -> None:
    """deploy command exits non-zero when core deploy raises SystemExit."""
    result = runner.invoke(app, ["deploy"])
    assert result.exit_code != 0


@patch(
    "brasa.commands.deploy.require_config",
    side_effect=SystemExit(1),
)
def test_deploy_command_config_missing(
    mock_config: MagicMock,
) -> None:
    """deploy command exits non-zero when config is missing."""
    result = runner.invoke(app, ["deploy"])
    assert result.exit_code != 0
