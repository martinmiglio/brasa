"""Unit tests for brasa.core.device — mpremote wrappers and DTR reset."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from brasa.core.device import (
    detect_board,
    device_firmware_info,
    dtr_reset,
    exec_expr,
    fs_cat,
    fs_cp,
    fs_ls,
    mpremote_run,
    repl,
    reset,
)

PORT = "/dev/cu.usbmodem1234"


def test_mpremote_run_capture(fp: pytest.fixture) -> None:
    """mpremote_run with capture=True returns stdout."""
    fp.register(
        ["mpremote", "connect", PORT, "exec", "print(1)"],
        returncode=0,
        stdout="1\n",
    )
    result = mpremote_run(PORT, "exec", "print(1)", capture=True)
    assert result.stdout == "1\n"


def test_mpremote_run_no_capture(fp: pytest.fixture) -> None:
    """mpremote_run with capture=False inherits stdio."""
    fp.register(
        ["mpremote", "connect", PORT, "repl"],
        returncode=0,
    )
    result = mpremote_run(PORT, "repl", capture=False)
    assert result.returncode == 0


def test_mpremote_run_raises_on_failure(fp: pytest.fixture) -> None:
    """mpremote_run raises CalledProcessError on non-zero exit."""
    fp.register(
        ["mpremote", "connect", PORT, "reset"],
        returncode=1,
        stderr="device not found",
    )
    with pytest.raises(subprocess.CalledProcessError):
        mpremote_run(PORT, "reset", capture=True)


def test_repl(fp: pytest.fixture) -> None:
    """repl() calls mpremote with 'repl'."""
    fp.register(["mpremote", "connect", PORT, "repl"], returncode=0)
    repl(PORT)
    assert fp.call_count(["mpremote", "connect", PORT, "repl"]) == 1


def test_reset(fp: pytest.fixture) -> None:
    """reset() calls mpremote with 'reset'."""
    fp.register(["mpremote", "connect", PORT, "reset"], returncode=0)
    reset(PORT)
    assert fp.call_count(["mpremote", "connect", PORT, "reset"]) == 1


def test_exec_expr(fp: pytest.fixture) -> None:
    """exec_expr() passes expression and returns output."""
    fp.register(
        ["mpremote", "connect", PORT, "exec", "print('hello')"],
        returncode=0,
        stdout="hello\n",
    )
    assert exec_expr(PORT, "print('hello')") == "hello\n"


def test_fs_cp(fp: pytest.fixture) -> None:
    """fs_cp() passes correct args."""
    fp.register(
        ["mpremote", "connect", PORT, "fs", "cp", "main.py", ":/main.py"],
        returncode=0,
    )
    fs_cp(PORT, "main.py", ":/main.py")
    assert (
        fp.call_count(["mpremote", "connect", PORT, "fs", "cp", "main.py", ":/main.py"])
        == 1
    )


def test_fs_cat(fp: pytest.fixture) -> None:
    """fs_cat() returns file contents."""
    fp.register(
        ["mpremote", "connect", PORT, "fs", "cat", ":/main.py"],
        returncode=0,
        stdout="print('hi')\n",
    )
    assert fs_cat(PORT, ":/main.py") == "print('hi')\n"


def test_fs_ls(fp: pytest.fixture) -> None:
    """fs_ls() returns directory listing."""
    fp.register(
        ["mpremote", "connect", PORT, "fs", "ls", "/"],
        returncode=0,
        stdout="main.py\nlib/\n",
    )
    assert fs_ls(PORT, "/") == "main.py\nlib/\n"


@patch("brasa.core.device.serial.Serial")
def test_dtr_reset(mock_serial_cls: MagicMock) -> None:
    """dtr_reset() toggles DTR on the serial port."""
    mock_ser = MagicMock()
    mock_serial_cls.return_value = mock_ser

    dtr_reset(PORT)

    mock_serial_cls.assert_called_once_with(PORT)
    assert mock_ser.dtr is True  # last assignment
    mock_ser.close.assert_called_once()


@patch("brasa.core.device.serial.Serial", side_effect=OSError("no port"))
def test_dtr_reset_catches_exceptions(mock_serial_cls: MagicMock) -> None:
    """dtr_reset() catches exceptions gracefully."""
    dtr_reset(PORT)  # should not raise


# ── detect_board ───────────────────────────────────────────────────────────


@patch("brasa.core.device.exec_expr", return_value="esp8266\n")
def test_detect_board_esp8266(mock_exec: MagicMock) -> None:
    assert detect_board(PORT) == "ESP8266_GENERIC"


@patch("brasa.core.device.exec_expr", return_value="esp32\n")
def test_detect_board_esp32(mock_exec: MagicMock) -> None:
    assert detect_board(PORT) == "ESP32_GENERIC"


@patch("brasa.core.device.exec_expr", return_value="rp2\n")
def test_detect_board_rp2(mock_exec: MagicMock) -> None:
    assert detect_board(PORT) == "RPI_PICO"


@patch("brasa.core.device.exec_expr", return_value="unknown_platform\n")
def test_detect_board_unknown_returns_none(mock_exec: MagicMock) -> None:
    assert detect_board(PORT) is None


@patch("brasa.core.device.exec_expr", side_effect=Exception("device not found"))
def test_detect_board_error_returns_none(mock_exec: MagicMock) -> None:
    assert detect_board(PORT) is None


# ── device_firmware_info ────────────────────────────────────────────────────


@patch("brasa.core.device.exec_expr", return_value="esp8266\n1.27.0\n")
def test_device_firmware_info(mock_exec: MagicMock) -> None:
    info = device_firmware_info(PORT)
    assert info["platform"] == "esp8266"
    assert info["board"] == "ESP8266_GENERIC"
    assert info["version"] == "1.27.0"


@patch("brasa.core.device.exec_expr", return_value="rp2\n1.27.0\n")
def test_device_firmware_info_rp2(mock_exec: MagicMock) -> None:
    info = device_firmware_info(PORT)
    assert info["board"] == "RPI_PICO"


@patch("brasa.core.device.exec_expr", return_value="unknown\n1.27.0\n")
def test_device_firmware_info_unknown_platform(mock_exec: MagicMock) -> None:
    info = device_firmware_info(PORT)
    assert info["board"] == "unknown"
