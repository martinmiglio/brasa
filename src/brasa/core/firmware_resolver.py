"""Firmware resolution — pure logic for resolving board, variant, version, and entries.

This module centralises the pure-function helpers that both ``firmware.py``
and ``firmware_index.py`` need, breaking the former circular dependency
between those two modules.

Note: ``find_entry_or_construct`` uses a deferred import of
``firmware_index`` because ``firmware_index`` already imports from this
module (for ``firmware_ext``), creating an unavoidable cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from brasa.core.config import BrasaConfig
from brasa.core.device import detect_board

if TYPE_CHECKING:
    from brasa.core.firmware_index import BoardIndex, FirmwareEntry


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


def resolve_board_from_config(cfg: BrasaConfig) -> str | None:
    """Extract board name from config if firmware is fully pinned (board + version)."""
    if cfg.firmware.board and cfg.firmware.version:
        return cfg.firmware.board
    return None


def resolve_board_from_device(port: str) -> str | None:
    """Detect board via device. Returns None if detection fails."""
    return detect_board(port)


def fill_from_config(
    cfg: BrasaConfig,
    board: str,
    variant: str | None,
    version: str | None,
) -> tuple[str | None, str | None]:
    """Fill variant/version from config only if config board matches resolved board.

    Returns the (possibly updated) variant and version.
    """
    if cfg.firmware.board != board:
        return variant, version
    if variant is None and cfg.firmware.variant:
        variant = cfg.firmware.variant
    if version is None and cfg.firmware.version:
        version = cfg.firmware.version
    return variant, version


def find_entry_or_construct(
    index: BoardIndex,
    board: str,
    variant: str,
    version: str,
    date: str,
) -> FirmwareEntry:
    """Find entry in index, falling back to constructing one from config values.

    Uses a deferred import to break the circular dependency with
    ``firmware_index`` (which imports ``firmware_ext`` from this module).
    """
    from brasa.core.firmware_index import FirmwareEntry as _FirmwareEntry
    from brasa.core.firmware_index import find_entry

    entry = find_entry(index, variant, version)
    if entry:
        return entry
    return _FirmwareEntry.from_config(board, variant, version, date)
