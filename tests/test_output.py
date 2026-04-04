"""Tests for brasa.core.output."""

import os

import pytest

from brasa.core.output import (
    cyan,
    dim,
    error,
    green,
    print_stdout,
    red,
    status,
    success,
    warn,
    yellow,
)

# ── Color helpers ────────────────────────────────────────────────────────────


def test_red_wraps_text() -> None:
    assert red("hello") == "\033[31mhello\033[0m"


def test_yellow_wraps_text() -> None:
    assert yellow("hello") == "\033[33mhello\033[0m"


def test_green_wraps_text() -> None:
    assert green("hello") == "\033[32mhello\033[0m"


def test_cyan_wraps_text() -> None:
    assert cyan("hello") == "\033[36mhello\033[0m"


def test_dim_wraps_text() -> None:
    assert dim("hello") == "\033[2mhello\033[0m"


# ── NO_COLOR ─────────────────────────────────────────────────────────────────


def test_no_color_strips_ansi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    assert red("hello") == "hello"
    assert green("hello") == "hello"
    assert cyan("hello") == "hello"
    assert dim("hello") == "hello"


def test_no_color_affects_status(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    status("test", "message")
    captured = capsys.readouterr()
    assert captured.err == "[test] message\n"
    assert "\033[" not in captured.err


# ── status() ─────────────────────────────────────────────────────────────────


def test_status_outputs_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    old = os.environ.pop("NO_COLOR", None)
    try:
        status("deploy", "uploading files")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "[deploy]" in captured.err
        assert "uploading files" in captured.err
    finally:
        if old is not None:
            os.environ["NO_COLOR"] = old


def test_status_uses_ansi_color(capsys: pytest.CaptureFixture[str]) -> None:
    old = os.environ.pop("NO_COLOR", None)
    try:
        status("info", "hello", color="\033[31m")
        captured = capsys.readouterr()
        assert "\033[31m[info]\033[0m hello\n" == captured.err
    finally:
        if old is not None:
            os.environ["NO_COLOR"] = old


# ── error / warn / success ───────────────────────────────────────────────────


def test_error_uses_red_tag(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    error("something broke")
    captured = capsys.readouterr()
    assert captured.err == "[error] something broke\n"


def test_warn_uses_yellow_tag(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    warn("careful")
    captured = capsys.readouterr()
    assert captured.err == "[warning] careful\n"


def test_success_uses_green_tag(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    success("done")
    captured = capsys.readouterr()
    assert captured.err == "[ok] done\n"


# ── print_stdout ─────────────────────────────────────────────────────────────


def test_print_stdout_outputs_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    print_stdout("serial data")
    captured = capsys.readouterr()
    assert captured.out == "serial data\n"
    assert captured.err == ""
