"""Tests for brasa.core.port — serial port detection."""

import json
import subprocess
from unittest.mock import MagicMock

import pytest

from brasa.core.port import _usb_tree_fallback, detect_port

# ── detect_port ─────────────────────────────────────────────────────────────


def test_single_port_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("brasa.core.port.glob.glob", lambda p: ["/dev/cu.usbserial-1"] if "usbserial" in p else [])
    assert detect_port() == "/dev/cu.usbserial-1"


def test_multiple_ports_warns_and_returns_first(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    ports = ["/dev/cu.usbserial-1", "/dev/cu.usbserial-2"]
    monkeypatch.setattr("brasa.core.port.glob.glob", lambda p: ports if "usbserial" in p else [])
    result = detect_port()
    assert result == "/dev/cu.usbserial-1"
    err = capsys.readouterr().err
    assert "multiple serial ports found" in err


def test_no_ports_triggers_fallback_and_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("brasa.core.port.glob.glob", lambda _p: [])
    monkeypatch.setattr("brasa.core.port._usb_tree_fallback", lambda: None)
    with pytest.raises(SystemExit, match="1"):
        detect_port()


def test_custom_patterns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("brasa.core.port.glob.glob", lambda p: ["/dev/ttyUSB0"] if "ttyUSB" in p else [])
    assert detect_port(patterns=["/dev/ttyUSB*"]) == "/dev/ttyUSB0"


# ── _usb_tree_fallback ─────────────────────────────────────────────────────


def _make_profiler_result(data: dict[str, object]) -> MagicMock:
    mock = MagicMock(spec=subprocess.CompletedProcess)
    mock.stdout = json.dumps(data)
    return mock


def test_fallback_known_vendor_suggests_driver(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    data = {"SPUSBDataType": [{"_name": "USB2.0-Ser!", "vendor_id": "0x1a86"}]}
    monkeypatch.setattr("brasa.core.port.subprocess.run", lambda *a, **kw: _make_profiler_result(data))
    _usb_tree_fallback()
    err = capsys.readouterr().err
    assert "CH340" in err
    assert "brew install" in err


def test_fallback_no_devices_suggests_cable(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    data: dict[str, object] = {"SPUSBDataType": []}
    monkeypatch.setattr("brasa.core.port.subprocess.run", lambda *a, **kw: _make_profiler_result(data))
    _usb_tree_fallback()
    err = capsys.readouterr().err
    assert "cable" in err


def test_fallback_timeout_handled(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def _raise_timeout(*_a: object, **_kw: object) -> None:
        raise subprocess.TimeoutExpired(cmd="system_profiler", timeout=10)

    monkeypatch.setattr("brasa.core.port.subprocess.run", _raise_timeout)
    _usb_tree_fallback()
    err = capsys.readouterr().err
    assert "could not query" in err
