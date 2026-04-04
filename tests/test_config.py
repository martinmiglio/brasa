"""Tests for brasa.core.config — config loading and validation."""

import dataclasses
from pathlib import Path

import pytest

from brasa.core.config import (
    BrasaConfig,
    DeployConfig,
    FirmwareConfig,
    PortConfig,
    SerialConfig,
    load_config,
    require_config,
)

_FULL_BRASA_TOML = """\
[firmware]
board = "ESP32"
variant = "GENERIC-SPIRAM"
version = "1.23.0"
date = "20240101"

[deploy]
src = "app"
env_file = ".env.prod"
boot_files = ["boot.py"]
romfs = false
mpy_compile = false

[serial]
baud_rate = 9600

[port]
patterns = ["/dev/cu.custom*"]
"""

_FULL_PYPROJECT_TOML = """\
[project]
name = "my-project"

[tool.brasa.firmware]
board = "ESP32"
variant = "GENERIC-SPIRAM"
version = "1.23.0"
date = "20240101"

[tool.brasa.deploy]
src = "app"
env_file = ".env.prod"
boot_files = ["boot.py"]
romfs = false
mpy_compile = false

[tool.brasa.serial]
baud_rate = 9600

[tool.brasa.port]
patterns = ["/dev/cu.custom*"]
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


def _assert_full_config(cfg: BrasaConfig) -> None:
    """Assert every field matches the full test TOML above."""
    assert cfg.firmware.board == "ESP32"
    assert cfg.firmware.variant == "GENERIC-SPIRAM"
    assert cfg.firmware.version == "1.23.0"
    assert cfg.firmware.date == "20240101"
    assert cfg.deploy.src == "app"
    assert cfg.deploy.env_file == ".env.prod"
    assert cfg.deploy.boot_files == ("boot.py",)
    assert cfg.deploy.romfs is False
    assert cfg.deploy.mpy_compile is False
    assert cfg.serial.baud_rate == 9600
    assert cfg.port.patterns == ("/dev/cu.custom*",)


# ── Loading sources ─────────────────────────────────────────────────────────


def test_load_from_brasa_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, "brasa.toml", _FULL_BRASA_TOML)
    monkeypatch.chdir(tmp_path)
    _assert_full_config(load_config())


def test_load_from_pyproject_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, "pyproject.toml", _FULL_PYPROJECT_TOML)
    monkeypatch.chdir(tmp_path)
    _assert_full_config(load_config())


def test_brasa_toml_takes_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, "brasa.toml", '[firmware]\nboard = "FROM_BRASA"\n')
    _write(tmp_path, "pyproject.toml", '[tool.brasa.firmware]\nboard = "FROM_PYPROJECT"\n')
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.firmware.board == "FROM_BRASA"


# ── No config ───────────────────────────────────────────────────────────────


def test_load_config_no_file_returns_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg == BrasaConfig()


def test_require_config_no_file_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="1"):
        require_config()


# ── Partial configs ─────────────────────────────────────────────────────────


def test_partial_config_firmware_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, "brasa.toml", '[firmware]\nboard = "RP2040"\n')
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.firmware.board == "RP2040"
    assert cfg.deploy == DeployConfig()
    assert cfg.serial == SerialConfig()
    assert cfg.port == PortConfig()


def test_partial_config_deploy_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, "brasa.toml", '[deploy]\nsrc = "lib"\n')
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.deploy.src == "lib"
    assert cfg.firmware == FirmwareConfig()


# ── Tuple conversions ───────────────────────────────────────────────────────


def test_boot_files_converted_to_tuple(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, "brasa.toml", '[deploy]\nboot_files = ["a.py", "b.py"]\n')
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.deploy.boot_files == ("a.py", "b.py")
    assert isinstance(cfg.deploy.boot_files, tuple)


def test_patterns_converted_to_tuple(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, "brasa.toml", '[port]\npatterns = ["/dev/ttyUSB*"]\n')
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.port.patterns == ("/dev/ttyUSB*",)
    assert isinstance(cfg.port.patterns, tuple)


# ── Defaults ────────────────────────────────────────────────────────────────


def test_default_values() -> None:
    cfg = BrasaConfig()
    assert cfg.firmware.board == "ESP8266"
    assert cfg.firmware.variant == "GENERIC"
    assert cfg.firmware.version == ""
    assert cfg.firmware.date == ""
    assert cfg.deploy.src == "src"
    assert cfg.deploy.env_file == ".env"
    assert cfg.deploy.boot_files == ("boot.py", "main.py")
    assert cfg.deploy.romfs is True
    assert cfg.deploy.mpy_compile is True
    assert cfg.serial.baud_rate == 115200
    assert cfg.port.patterns == (
        "/dev/cu.usbserial*",
        "/dev/cu.wchusbserial*",
        "/dev/cu.SLAB_USBtoUART*",
    )


# ── Frozen dataclass ────────────────────────────────────────────────────────


def test_frozen_dataclass() -> None:
    cfg = BrasaConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.firmware = FirmwareConfig(board="X")  # type: ignore[misc]


# ── Edge cases ──────────────────────────────────────────────────────────────


def test_empty_brasa_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, "brasa.toml", "")
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg == BrasaConfig()


def test_unknown_keys_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, "brasa.toml", '[firmware]\nboard = "ESP32"\nunknown_key = 42\n')
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.firmware.board == "ESP32"
