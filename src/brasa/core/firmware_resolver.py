"""Pure helpers for firmware resolution — shared by firmware.py and firmware_index.py."""

from brasa.core.config import BrasaConfig


def firmware_ext(board: str) -> str:
    """Infer firmware file extension from board name."""
    upper = board.upper()
    if any(prefix in upper for prefix in ("RPI_PICO", "RP2", "ARDUINO_NANO_RP")):
        return "uf2"
    return "bin"


def firmware_filename(board: str, variant: str, version: str, date: str) -> str:
    """Build the firmware binary filename from components."""
    ext = firmware_ext(board)
    if variant:
        return f"{board}-{variant}-{date}-v{version}.{ext}"
    return f"{board}-{date}-v{version}.{ext}"


def fill_from_config(
    cfg: BrasaConfig,
    board: str,
    variant: str | None,
    version: str | None,
) -> tuple[str | None, str | None]:
    """Fill variant/version from config only if config board matches resolved board."""
    if cfg.firmware.board != board:
        return variant, version
    if variant is None and cfg.firmware.variant:
        variant = cfg.firmware.variant
    if version is None and cfg.firmware.version:
        version = cfg.firmware.version
    return variant, version
