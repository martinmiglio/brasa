"""Smoke tests for the brasa CLI."""

from typer.testing import CliRunner

from brasa.cli import app

runner = CliRunner()


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "brasa" in result.output


def test_help_flag():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "MicroPython" in result.output
