"""Project configuration loading from brasa.toml or pyproject.toml."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from brasa.core.output import error


@dataclass(frozen=True)
class FirmwareConfig:
    """Firmware flashing settings."""

    board: str = "ESP8266"
    variant: str = "GENERIC"
    version: str = ""
    date: str = ""


@dataclass(frozen=True)
class DeployConfig:
    """Code deployment settings."""

    src: str = "src"
    env_file: str = ".env"
    boot_files: tuple[str, ...] = ("boot.py", "main.py")
    romfs: bool = True
    mpy_compile: bool = True


@dataclass(frozen=True)
class SerialConfig:
    """Serial communication settings."""

    baud_rate: int = 115200


@dataclass(frozen=True)
class PortConfig:
    """Serial port detection settings."""

    patterns: tuple[str, ...] = (
        "/dev/cu.usbserial*",
        "/dev/cu.wchusbserial*",
        "/dev/cu.SLAB_USBtoUART*",
    )


@dataclass(frozen=True)
class BrasaConfig:
    """Top-level project configuration."""

    firmware: FirmwareConfig = field(default_factory=FirmwareConfig)
    deploy: DeployConfig = field(default_factory=DeployConfig)
    serial: SerialConfig = field(default_factory=SerialConfig)
    port: PortConfig = field(default_factory=PortConfig)


def _find_config_file() -> tuple[Path | None, dict]:
    """Locate and parse the nearest config file.

    Checks CWD for ``brasa.toml`` first, then falls back to
    ``[tool.brasa]`` inside ``pyproject.toml``.  Returns the path and
    the parsed brasa-specific data dict, or ``(None, {})`` when neither
    source is found.
    """
    cwd = Path.cwd()

    brasa_toml = cwd / "brasa.toml"
    if brasa_toml.is_file():
        with brasa_toml.open("rb") as f:
            data = tomllib.load(f)
        return brasa_toml, data

    pyproject_toml = cwd / "pyproject.toml"
    if pyproject_toml.is_file():
        with pyproject_toml.open("rb") as f:
            data = tomllib.load(f)
        brasa_section = data.get("tool", {}).get("brasa")
        if brasa_section is not None:
            return pyproject_toml, brasa_section

    return None, {}


def _parse_config(data: dict) -> BrasaConfig:
    """Build a :class:`BrasaConfig` from a raw TOML dict.

    Missing sections and keys fall back to dataclass defaults.  TOML
    lists for ``boot_files`` and ``patterns`` are converted to tuples.
    """
    fw_raw = data.get("firmware", {})
    firmware = FirmwareConfig(**{k: v for k, v in fw_raw.items() if k in FirmwareConfig.__dataclass_fields__})

    deploy_raw = data.get("deploy", {})
    if "boot_files" in deploy_raw and isinstance(deploy_raw["boot_files"], list):
        deploy_raw = {**deploy_raw, "boot_files": tuple(deploy_raw["boot_files"])}
    deploy = DeployConfig(**{k: v for k, v in deploy_raw.items() if k in DeployConfig.__dataclass_fields__})

    serial_raw = data.get("serial", {})
    serial = SerialConfig(**{k: v for k, v in serial_raw.items() if k in SerialConfig.__dataclass_fields__})

    port_raw = data.get("port", {})
    if "patterns" in port_raw and isinstance(port_raw["patterns"], list):
        port_raw = {**port_raw, "patterns": tuple(port_raw["patterns"])}
    port = PortConfig(**{k: v for k, v in port_raw.items() if k in PortConfig.__dataclass_fields__})

    return BrasaConfig(firmware=firmware, deploy=deploy, serial=serial, port=port)


def load_config() -> BrasaConfig:
    """Load project config, returning all defaults when no file is found."""
    _, data = _find_config_file()
    if not data:
        return BrasaConfig()
    return _parse_config(data)


def require_config() -> BrasaConfig:
    """Load project config, exiting with an error when no file is found."""
    path, data = _find_config_file()
    if path is None:
        error("no brasa.toml or [tool.brasa] in pyproject.toml found")
        raise SystemExit(1)
    return _parse_config(data)
