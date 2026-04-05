"""Tests for CLI commands: detect, serial, repl, restart, exec."""

from contextlib import nullcontext
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from brasa.cli import app

runner = CliRunner()


# ── detect ──────────────────────────────────────────────────────────────────


def test_detect_with_port_override() -> None:
    result = runner.invoke(app, ["--port", "/dev/ttyUSB0", "detect"])
    assert result.exit_code == 0
    assert "/dev/ttyUSB0" in result.output


@patch("brasa.commands.detect.resolve_port", return_value="/dev/cu.autodetected")
def test_detect_auto(mock_detect: MagicMock) -> None:
    result = runner.invoke(app, ["detect"])
    assert result.exit_code == 0
    assert "/dev/cu.autodetected" in result.output


@patch(
    "brasa.commands.detect.resolve_port",
    side_effect=SystemExit(1),
)
def test_detect_no_device_found(mock_detect: MagicMock) -> None:
    result = runner.invoke(app, ["detect"])
    assert result.exit_code != 0


# ── serial ──────────────────────────────────────────────────────────────────


@patch("brasa.commands.serial.SerialReader")
@patch("brasa.commands.serial.port_lock", return_value=nullcontext())
@patch("brasa.commands.serial.resolve_port", return_value="/dev/cu.test")
def test_serial(
    mock_detect: MagicMock, mock_lock: MagicMock, mock_reader_cls: MagicMock
) -> None:
    result = runner.invoke(app, ["serial"])
    assert result.exit_code == 0


@patch("brasa.commands.serial.SerialReader")
@patch("brasa.commands.serial.port_lock", return_value=nullcontext())
def test_serial_with_port_and_baud(
    mock_lock: MagicMock, mock_reader_cls: MagicMock
) -> None:
    result = runner.invoke(app, ["--port", "/dev/ttyS0", "serial", "--baud", "9600"])
    assert result.exit_code == 0


# ── repl ────────────────────────────────────────────────────────────────────


@patch("brasa.commands.repl.device_repl")
@patch("brasa.commands.repl.port_lock", return_value=nullcontext())
@patch("brasa.commands.repl.resolve_port", return_value="/dev/cu.test")
def test_repl(
    mock_detect: MagicMock, mock_lock: MagicMock, mock_repl: MagicMock
) -> None:
    result = runner.invoke(app, ["repl"])
    assert result.exit_code == 0


@patch("brasa.commands.repl.device_repl")
@patch("brasa.commands.repl.port_lock", return_value=nullcontext())
def test_repl_with_port_override(mock_lock: MagicMock, mock_repl: MagicMock) -> None:
    result = runner.invoke(app, ["--port", "/dev/cu.custom", "repl"])
    assert result.exit_code == 0


# ── restart ─────────────────────────────────────────────────────────────────


@patch("brasa.commands.restart.port_lock", return_value=nullcontext())
@patch("brasa.commands.restart.reset")
@patch("brasa.commands.restart.resolve_port", return_value="/dev/cu.test")
def test_restart(
    mock_detect: MagicMock, mock_reset: MagicMock, mock_lock: MagicMock
) -> None:
    result = runner.invoke(app, ["restart"])
    assert result.exit_code == 0
    assert "restarted" in (result.output + (result.stderr if result.stderr else ""))


@patch("brasa.commands.restart.port_lock", return_value=nullcontext())
@patch("brasa.commands.restart.reset")
def test_restart_with_port_override(
    mock_reset: MagicMock, mock_lock: MagicMock
) -> None:
    result = runner.invoke(app, ["--port", "/dev/cu.manual", "restart"])
    assert result.exit_code == 0
    assert "restarted" in (result.output + (result.stderr if result.stderr else ""))


@patch("brasa.commands.restart.port_lock", return_value=nullcontext())
@patch("brasa.commands.restart.reset", side_effect=RuntimeError("connection lost"))
@patch("brasa.commands.restart.resolve_port", return_value="/dev/cu.test")
def test_restart_failure(
    mock_detect: MagicMock, mock_reset: MagicMock, mock_lock: MagicMock
) -> None:
    result = runner.invoke(app, ["restart"])
    assert result.exit_code != 0


# ── exec ────────────────────────────────────────────────────────────────────


@patch("brasa.commands.exec.port_lock", return_value=nullcontext())
@patch("brasa.commands.exec.exec_expr", return_value="42")
@patch("brasa.commands.exec.resolve_port", return_value="/dev/cu.test")
def test_exec(
    mock_detect: MagicMock, mock_exec: MagicMock, mock_lock: MagicMock
) -> None:
    result = runner.invoke(app, ["exec", "print(1)"])
    assert result.exit_code == 0
    assert "42" in result.output


@patch("brasa.commands.exec.port_lock", return_value=nullcontext())
@patch("brasa.commands.exec.exec_expr", return_value="")
@patch("brasa.commands.exec.resolve_port", return_value="/dev/cu.test")
def test_exec_empty_result(
    mock_detect: MagicMock, mock_exec: MagicMock, mock_lock: MagicMock
) -> None:
    result = runner.invoke(app, ["exec", "pass"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


@patch("brasa.commands.exec.port_lock", return_value=nullcontext())
@patch("brasa.commands.exec.exec_expr", return_value="hello")
def test_exec_with_port_override(mock_exec: MagicMock, mock_lock: MagicMock) -> None:
    result = runner.invoke(app, ["--port", "/dev/cu.manual", "exec", "expr"])
    assert result.exit_code == 0
    assert "hello" in result.output
