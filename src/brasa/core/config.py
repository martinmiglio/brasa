"""Project configuration loading from brasa.toml or pyproject.toml."""

import dataclasses
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from brasa.core.output import error


@dataclass(frozen=True)
class FirmwareConfig:
    """Firmware flashing settings."""

    board: str = "ESP8266_GENERIC"
    variant: str = ""
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

    @property
    def excluded_filenames(self) -> set[str]:
        """Return bare filenames that should be excluded from source deploys."""
        return {Path(name).name for name in self.boot_files} | {
            Path(self.env_file).name
        }


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
        try:
            with brasa_toml.open("rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            error(f"malformed config: {exc}")
            raise SystemExit(1)
        return brasa_toml, data

    pyproject_toml = cwd / "pyproject.toml"
    if pyproject_toml.is_file():
        try:
            with pyproject_toml.open("rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            error(f"malformed config: {exc}")
            raise SystemExit(1)
        brasa_section = data.get("tool", {}).get("brasa")
        if brasa_section is not None:
            return pyproject_toml, brasa_section

    return None, {}


def resolve_config_write_path() -> Path:
    """Return the config file to write to.

    Uses the same resolution as reading: ``brasa.toml`` first, then
    ``pyproject.toml`` with ``[tool.brasa]``.  When neither has brasa
    config, defaults to ``pyproject.toml`` in the current directory.
    """
    path, _ = _find_config_file()
    if path is not None:
        return path
    return Path.cwd() / "pyproject.toml"


def _parse_section[T](cls: type[T], raw: dict) -> T:
    """Construct a frozen dataclass from a raw TOML dict.

    Unknown keys are silently ignored and TOML lists are converted to
    tuples for tuple-typed fields.
    """
    known = {f.name for f in dataclasses.fields(cls)}
    kwargs: dict[str, object] = {}
    for k, v in raw.items():
        if k not in known:
            continue
        if isinstance(v, list):
            kwargs[k] = tuple(v)
        else:
            kwargs[k] = v
    return cls(**kwargs)  # type: ignore[call-arg]


def _parse_config(data: dict) -> BrasaConfig:
    """Build a :class:`BrasaConfig` from a raw TOML dict.

    Missing sections and keys fall back to dataclass defaults.  TOML
    lists for ``boot_files`` and ``patterns`` are converted to tuples.
    """
    return BrasaConfig(
        firmware=_parse_section(FirmwareConfig, data.get("firmware", {})),
        deploy=_parse_section(DeployConfig, data.get("deploy", {})),
        serial=_parse_section(SerialConfig, data.get("serial", {})),
        port=_parse_section(PortConfig, data.get("port", {})),
    )


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
