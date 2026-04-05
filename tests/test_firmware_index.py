"""Tests for brasa.core.firmware_index — HTML scraping, caching, queries."""

import json
import os
import re
import time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from brasa.core.firmware_index import (
    BoardIndex,
    BoardInfo,
    FirmwareEntry,
    _BoardLinkParser,
    _is_fresh,
    _parse_firmware_href,
    cache_dir,
    fetch_board_index,
    fetch_board_list,
    find_entry,
    list_variants,
    list_versions,
)

# ── HTML parser ─────────────────────────────────────────────────────────────

_SAMPLE_HTML = """
<html><body>
<h2>Releases</h2>
<a href="/resources/firmware/ESP32_GENERIC-20251209-v1.27.0.bin">v1.27.0</a>
<a href="/resources/firmware/ESP32_GENERIC-SPIRAM-20251209-v1.27.0.bin">v1.27.0</a>
<a href="/resources/firmware/ESP32_GENERIC-20250911-v1.26.1.bin">v1.26.1</a>
<a href="/resources/firmware/ESP32_GENERIC-20251209-v1.27.0.elf">elf</a>
<a href="/resources/firmware/ESP32_GENERIC-20251209-v1.27.0.map">map</a>
<h2>Preview builds</h2>
<a href="/resources/firmware/ESP32_GENERIC-20260401-v1.28.0-preview.314.ge8a3ee0342.bin">preview</a>
<a href="https://github.com/micropython/micropython">GitHub</a>
</body></html>
"""


def test_regex_extracts_firmware_hrefs() -> None:
    hrefs = re.findall(r'href="([^"]*?/resources/firmware/[^"]*)"', _SAMPLE_HTML)
    assert len(hrefs) == 6  # 4 .bin + 1 .elf + 1 .map


def test_regex_ignores_non_firmware_links() -> None:
    html = '<a href="https://github.com">GH</a><a href="/download/">dl</a>'
    hrefs = re.findall(r'href="([^"]*?/resources/firmware/[^"]*)"', html)
    assert hrefs == []


# ── _parse_firmware_href ────────────────────────────────────────────────────


def test_parse_stable_no_variant() -> None:
    entry = _parse_firmware_href(
        "/resources/firmware/ESP32_GENERIC-20251209-v1.27.0.bin", "ESP32_GENERIC"
    )
    assert entry is not None
    assert entry.board == "ESP32_GENERIC"
    assert entry.variant == ""
    assert entry.version == "1.27.0"
    assert entry.date == "20251209"
    assert entry.ext == "bin"
    assert not entry.is_preview


def test_parse_stable_with_variant() -> None:
    entry = _parse_firmware_href(
        "/resources/firmware/ESP32_GENERIC-SPIRAM-20251209-v1.27.0.bin", "ESP32_GENERIC"
    )
    assert entry is not None
    assert entry.variant == "SPIRAM"


def test_parse_preview_build() -> None:
    entry = _parse_firmware_href(
        "/resources/firmware/ESP32_GENERIC-20260401-v1.28.0-preview.314.ge8a3ee0342.bin",
        "ESP32_GENERIC",
    )
    assert entry is not None
    assert entry.is_preview
    assert entry.version == "1.28.0-preview.314.ge8a3ee0342"


def test_parse_uf2() -> None:
    entry = _parse_firmware_href(
        "/resources/firmware/RPI_PICO-20251209-v1.27.0.uf2", "RPI_PICO"
    )
    assert entry is not None
    assert entry.ext == "uf2"


def test_parse_ignores_elf() -> None:
    entry = _parse_firmware_href(
        "/resources/firmware/ESP32_GENERIC-20251209-v1.27.0.elf", "ESP32_GENERIC"
    )
    assert entry is None


def test_parse_ignores_wrong_board() -> None:
    entry = _parse_firmware_href(
        "/resources/firmware/ESP32_GENERIC-20251209-v1.27.0.bin", "ESP8266_GENERIC"
    )
    assert entry is None


def test_parse_multi_segment_variant() -> None:
    entry = _parse_firmware_href(
        "/resources/firmware/ESP8266_GENERIC-FLASH_2M_ROMFS-20251209-v1.27.0.bin",
        "ESP8266_GENERIC",
    )
    assert entry is not None
    assert entry.variant == "FLASH_2M_ROMFS"


# ── cache_dir ───────────────────────────────────────────────────────────────


def test_cache_dir_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRASA_CACHE_DIR", raising=False)
    d = cache_dir()
    assert d == Path.home() / ".cache" / "brasa" / "firmware"


def test_cache_dir_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRASA_CACHE_DIR", "/tmp/custom-cache")
    d = cache_dir()
    assert d == Path("/tmp/custom-cache")


# ── _is_fresh ───────────────────────────────────────────────────────────────


def test_is_fresh_true(tmp_path: Path) -> None:
    p = tmp_path / "test.json"
    p.write_text("{}")
    assert _is_fresh(p)


def test_is_fresh_false_missing(tmp_path: Path) -> None:
    assert not _is_fresh(tmp_path / "missing.json")


# ── list_variants / list_versions ───────────────────────────────────────────

_ENTRIES = (
    FirmwareEntry("ESP32_GENERIC", "", "1.27.0", "20251209", "f1.bin", "url1", "bin"),
    FirmwareEntry("ESP32_GENERIC", "", "1.26.1", "20250911", "f2.bin", "url2", "bin"),
    FirmwareEntry(
        "ESP32_GENERIC", "SPIRAM", "1.27.0", "20251209", "f3.bin", "url3", "bin"
    ),
    FirmwareEntry(
        "ESP32_GENERIC",
        "",
        "1.28.0-preview.1.gabc",
        "20260401",
        "f4.bin",
        "url4",
        "bin",
    ),
)
_INDEX = BoardIndex(board="ESP32_GENERIC", entries=_ENTRIES, fetched_at=time.time())


def test_list_variants() -> None:
    variants = list_variants(_INDEX)
    assert variants == ["", "SPIRAM"]


def test_list_versions_default_variant() -> None:
    versions = list_versions(_INDEX, "")
    assert versions == ["1.27.0", "1.26.1"]


def test_list_versions_with_preview() -> None:
    versions = list_versions(_INDEX, "", include_preview=True)
    assert "1.28.0-preview.1.gabc" in versions


def test_list_versions_spiram() -> None:
    versions = list_versions(_INDEX, "SPIRAM")
    assert versions == ["1.27.0"]


# ── find_entry ──────────────────────────────────────────────────────────────


def test_find_entry_found() -> None:
    entry = find_entry(_INDEX, "", "1.27.0")
    assert entry is not None
    assert entry.filename == "f1.bin"


def test_find_entry_not_found() -> None:
    assert find_entry(_INDEX, "", "9.9.9") is None


# ── fetch_board_index ───────────────────────────────────────────────────────


def _write_board_cache(
    tmp_path: Path, board: str, entries: tuple[FirmwareEntry, ...]
) -> Path:
    """Write a valid board index cache file and return its path."""
    cache_file = tmp_path / f"{board}.index.json"
    data = {
        "board": board,
        "fetched_at": time.time(),
        "entries": [asdict(e) for e in entries],
    }
    cache_file.write_text(json.dumps(data))
    return cache_file


@patch("brasa.core.firmware_index._scrape_board_page")
def test_fetch_uses_cache_when_fresh(
    mock_scrape: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRASA_CACHE_DIR", str(tmp_path))
    _write_board_cache(tmp_path, "ESP32_GENERIC", _ENTRIES)

    result = fetch_board_index("ESP32_GENERIC")

    mock_scrape.assert_not_called()
    assert result.board == "ESP32_GENERIC"
    assert len(result.entries) == len(_ENTRIES)
    assert result.entries[0].version == "1.27.0"


@patch("brasa.core.firmware_index._scrape_board_page", return_value=list(_ENTRIES))
def test_fetch_scrapes_when_stale(
    mock_scrape: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRASA_CACHE_DIR", str(tmp_path))
    cache_file = _write_board_cache(tmp_path, "ESP32_GENERIC", _ENTRIES)
    # Make the file stale (older than 1 hour)
    stale_time = time.time() - 7200
    os.utime(cache_file, (stale_time, stale_time))

    result = fetch_board_index("ESP32_GENERIC")

    mock_scrape.assert_called_once_with("ESP32_GENERIC")
    assert result.board == "ESP32_GENERIC"
    assert len(result.entries) == len(_ENTRIES)
    # Verify the cache file was updated (mtime should be recent)
    assert cache_file.stat().st_mtime > stale_time


@patch("brasa.core.firmware_index._scrape_board_page", return_value=list(_ENTRIES))
def test_fetch_force_refresh(
    mock_scrape: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRASA_CACHE_DIR", str(tmp_path))
    _write_board_cache(tmp_path, "ESP32_GENERIC", _ENTRIES)

    fetch_board_index("ESP32_GENERIC", force_refresh=True)

    mock_scrape.assert_called_once()


@patch("brasa.core.firmware_index._scrape_board_page", return_value=list(_ENTRIES))
def test_corrupted_cache_triggers_rescrape(
    mock_scrape: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRASA_CACHE_DIR", str(tmp_path))
    cache_file = tmp_path / "ESP32_GENERIC.index.json"
    cache_file.write_text("not valid json {{{")

    result = fetch_board_index("ESP32_GENERIC")

    mock_scrape.assert_called()
    assert result.board == "ESP32_GENERIC"
    assert len(result.entries) == len(_ENTRIES)


# ── Board list scraping ────────────────────────────────────────────────────

_BOARD_LIST_HTML = """
<html><body>
<a href="ESP32_GENERIC">ESP32 / WROOM Espressif</a>
<a href="ESP8266_GENERIC">ESP8266 Espressif</a>
<a href="RPI_PICO">Pico Raspberry Pi</a>
<a href="https://github.com">GitHub</a>
<a href="/download/">Downloads</a>
</body></html>
"""


def test_board_link_parser() -> None:
    parser = _BoardLinkParser()
    parser.feed(_BOARD_LIST_HTML)
    assert len(parser.boards) == 3
    ids = [b[0] for b in parser.boards]
    assert "ESP32_GENERIC" in ids
    assert "RPI_PICO" in ids


def test_board_link_parser_ignores_non_board_links() -> None:
    parser = _BoardLinkParser()
    parser.feed('<a href="https://github.com">GH</a><a href="/download/">dl</a>')
    assert parser.boards == []


_BOARD_LIST = [
    BoardInfo("ESP32_GENERIC", "ESP32 / WROOM"),
    BoardInfo("RPI_PICO", "Pico"),
]


def _write_board_list_cache(tmp_path: Path, boards: list[BoardInfo]) -> Path:
    """Write a valid board list cache file and return its path."""
    cache_file = tmp_path / "boards.json"
    data = {
        "fetched_at": time.time(),
        "boards": [{"id": b.id, "name": b.name} for b in boards],
    }
    cache_file.write_text(json.dumps(data))
    return cache_file


@patch("brasa.core.firmware_index._scrape_board_list")
def test_fetch_board_list_uses_cache(
    mock_scrape: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRASA_CACHE_DIR", str(tmp_path))
    _write_board_list_cache(tmp_path, _BOARD_LIST)

    result = fetch_board_list()

    mock_scrape.assert_not_called()
    assert len(result) == 2
    assert result[0].id == "ESP32_GENERIC"


@patch("brasa.core.firmware_index._scrape_board_list", return_value=_BOARD_LIST)
def test_fetch_board_list_scrapes_when_stale(
    mock_scrape: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRASA_CACHE_DIR", str(tmp_path))
    cache_file = _write_board_list_cache(tmp_path, _BOARD_LIST)
    stale_time = time.time() - 7200
    os.utime(cache_file, (stale_time, stale_time))

    result = fetch_board_list()

    assert len(result) == 2
    mock_scrape.assert_called_once()


@patch("brasa.core.firmware_index._scrape_board_list", return_value=_BOARD_LIST)
def test_corrupted_board_list_cache_triggers_rescrape(
    mock_scrape: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRASA_CACHE_DIR", str(tmp_path))
    cache_file = tmp_path / "boards.json"
    cache_file.write_text("not valid json {{{")

    result = fetch_board_list()

    mock_scrape.assert_called_once()
    assert len(result) == 2
    assert result[0].id == "ESP32_GENERIC"


# ── Empty-result guard ─────────────────────────────────────────────────────


@patch("brasa.core.firmware_index._scrape_board_page", return_value=[])
def test_empty_scrape_skips_cache_write(
    mock_scrape: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRASA_CACHE_DIR", str(tmp_path))
    cache_file = tmp_path / "ESP32_GENERIC.index.json"

    result = fetch_board_index("ESP32_GENERIC")

    mock_scrape.assert_called_once()
    assert len(result.entries) == 0
    assert not cache_file.exists()


@patch("brasa.core.firmware_index._scrape_board_list", return_value=[])
def test_empty_board_list_scrape_skips_cache_write(
    mock_scrape: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRASA_CACHE_DIR", str(tmp_path))
    cache_file = tmp_path / "boards.json"

    result = fetch_board_list()

    mock_scrape.assert_called_once()
    assert result == []
    assert not cache_file.exists()
