"""Firmware index — scrape micropython.org for available firmware and cache locally."""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import TypeVar

import httpx

from brasa.core import output
from brasa.core.firmware_resolver import firmware_ext, firmware_filename

_T = TypeVar("_T")

_BASE_URL = "https://micropython.org"
_INDEX_TTL = 3600  # 1 hour

_FILENAME_RE = re.compile(
    r"^(?P<board>[A-Z0-9_]+?)"
    r"(?:-(?P<variant>[A-Z0-9_]+?))?"
    r"-(?P<date>\d{8})"
    r"-v(?P<version>\d+\.\d+\.\d+(?:-preview\.\d+\.\w+)?)"
    r"\.(?P<ext>bin|uf2|dfu)$"
)


@dataclass(frozen=True)
class FirmwareEntry:
    """A single downloadable firmware file."""

    board: str
    variant: str
    version: str
    date: str
    filename: str
    url: str
    ext: str

    @property
    def is_preview(self) -> bool:
        return "preview" in self.version

    @classmethod
    def from_config(
        cls, board: str, variant: str, version: str, date: str
    ) -> FirmwareEntry:
        """Build a FirmwareEntry from config values, inferring filename and URL."""
        ext = firmware_ext(board)
        filename = firmware_filename(board, variant, version, date)
        return cls(
            board=board,
            variant=variant,
            version=version,
            date=date,
            filename=filename,
            url=f"{_BASE_URL}/resources/firmware/{filename}",
            ext=ext,
        )


@dataclass(frozen=True)
class BoardIndex:
    """Cached firmware index for a single board."""

    board: str
    entries: tuple[FirmwareEntry, ...]
    fetched_at: float


def cache_dir() -> Path:
    """Return the firmware cache directory."""
    override = os.environ.get("BRASA_CACHE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "brasa" / "firmware"


def _index_path(board: str) -> Path:
    """Return path to the JSON index file for a board."""
    return cache_dir() / f"{board}.index.json"


def _is_fresh(path: Path) -> bool:
    """Check if a cache file exists and is within TTL."""
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < _INDEX_TTL


def _parse_firmware_href(href: str, board: str) -> FirmwareEntry | None:
    """Parse a firmware download href into a FirmwareEntry, or None if it doesn't match."""
    filename = href.rsplit("/", 1)[-1]
    m = _FILENAME_RE.match(filename)
    if not m:
        return None
    parsed_board = m.group("board")
    if parsed_board != board:
        return None
    return FirmwareEntry(
        board=parsed_board,
        variant=m.group("variant") or "",
        version=m.group("version"),
        date=m.group("date"),
        filename=filename,
        url=f"{_BASE_URL}{href}" if href.startswith("/") else href,
        ext=m.group("ext"),
    )


def _scrape_board_page(board: str) -> list[FirmwareEntry]:
    """Fetch a board's download page and extract firmware entries."""
    url = f"{_BASE_URL}/download/{board}/"
    output.status("firmware", f"fetching index for {board}")
    try:
        response = httpx.get(url, follow_redirects=True, timeout=30)
    except httpx.TimeoutException:
        output.error(f"timed out fetching firmware index for {board}")
        raise SystemExit(1)
    except httpx.ConnectError as exc:
        output.error(f"connection failed fetching firmware index: {exc}")
        raise SystemExit(1)
    if response.status_code == 404:
        output.error(
            f"board '{board}' not found on micropython.org — "
            "run 'brasa firmware list' with a valid board identifier "
            "(e.g. ESP8266_GENERIC, ESP32_GENERIC, RPI_PICO)"
        )
        raise SystemExit(1)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        output.error(f"failed to fetch firmware index: HTTP {exc.response.status_code}")
        raise SystemExit(1)

    hrefs = re.findall(r'href="([^"]*?/resources/firmware/[^"]*)"', response.text)

    entries: list[FirmwareEntry] = []
    seen: set[str] = set()
    for href in hrefs:
        entry = _parse_firmware_href(href, board)
        if entry and entry.filename not in seen:
            seen.add(entry.filename)
            entries.append(entry)
    return entries


def _cached_fetch(
    path: Path,
    scrape_fn: Callable[[], _T],
    load_fn: Callable[[Path], _T],
    save_fn: Callable[[Path, _T], None],
    label: str,
    *,
    force_refresh: bool = False,
) -> _T:
    """Generic cache-or-scrape helper used by board index and board list fetchers."""
    if not force_refresh and _is_fresh(path):
        output.status("firmware", f"using cached {label}")
        try:
            return load_fn(path)
        except (json.JSONDecodeError, KeyError):
            output.warn(f"corrupted cache for {label}, re-fetching")
            path.unlink(missing_ok=True)

    data = scrape_fn()
    if not data:
        output.warn(f"scrape returned no results for {label} — skipping cache write")
        return data
    save_fn(path, data)
    return data


def _save_board_index(path: Path, entries: list[FirmwareEntry]) -> None:
    """Save a board index to the JSON cache."""
    board = entries[0].board
    now = time.time()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "board": board,
        "fetched_at": now,
        "entries": [asdict(e) for e in entries],
    }
    try:
        path.write_text(json.dumps(data, indent=2))
    except OSError as exc:
        output.warn(f"could not cache firmware index: {exc}")


def _load_board_index(path: Path) -> list[FirmwareEntry]:
    """Load a board index from the JSON cache and return the entry list."""
    data = json.loads(path.read_text())
    return [FirmwareEntry(**e) for e in data["entries"]]


def fetch_board_index(board: str, *, force_refresh: bool = False) -> BoardIndex:
    """Return firmware entries for a board, using cache when fresh."""
    path = _index_path(board)
    entries = _cached_fetch(
        path,
        scrape_fn=lambda: _scrape_board_page(board),
        load_fn=_load_board_index,
        save_fn=_save_board_index,
        label=f"index for {board}",
        force_refresh=force_refresh,
    )
    fetched_at = path.stat().st_mtime if path.exists() else time.time()
    return BoardIndex(board=board, entries=tuple(entries), fetched_at=fetched_at)


def list_variants(index: BoardIndex) -> list[str]:
    """Extract unique variant names from a board index, sorted alphabetically."""
    variants = sorted({e.variant for e in index.entries})
    return variants


def list_versions(
    index: BoardIndex, variant: str = "", *, include_preview: bool = False
) -> list[str]:
    """Extract unique versions for a variant, sorted newest first."""
    versions: list[str] = []
    seen: set[str] = set()
    for entry in index.entries:
        if entry.variant != variant:
            continue
        if not include_preview and entry.is_preview:
            continue
        if entry.version not in seen:
            seen.add(entry.version)
            versions.append(entry.version)
    return versions


def find_entry(index: BoardIndex, variant: str, version: str) -> FirmwareEntry | None:
    """Find a specific firmware entry by variant and version."""
    for entry in index.entries:
        if entry.variant == variant and entry.version == version:
            return entry
    return None


def find_entry_or_construct(
    index: BoardIndex,
    board: str,
    variant: str,
    version: str,
    date: str,
) -> FirmwareEntry:
    """Find entry in index, falling back to constructing one from config values."""
    entry = find_entry(index, variant, version)
    if entry:
        return entry
    return FirmwareEntry.from_config(board, variant, version, date)


# ── Global board list ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class BoardInfo:
    """A board available on micropython.org."""

    id: str
    name: str


class _BoardLinkParser(HTMLParser):
    """Extract board IDs and names from micropython.org/download/."""

    def __init__(self) -> None:
        super().__init__()
        self.boards: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self._in_board_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value and re.fullmatch(r"[A-Z0-9_]+", value):
                self._in_board_link = True
                self._current_href = value
                self._current_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_board_link:
            name = " ".join(self._current_text).strip()
            if self._current_href:
                self.boards.append((self._current_href, name))
            self._in_board_link = False
            self._current_href = None

    def handle_data(self, data: str) -> None:
        if self._in_board_link:
            self._current_text.append(data.strip())


def _board_list_path() -> Path:
    """Return path to the cached board list JSON."""
    return cache_dir() / "boards.json"


def _scrape_board_list() -> list[BoardInfo]:
    """Fetch micropython.org/download/ and extract available boards."""
    url = f"{_BASE_URL}/download/"
    output.status("firmware", "fetching board list")
    try:
        response = httpx.get(url, follow_redirects=True, timeout=30)
    except httpx.TimeoutException:
        output.error("timed out fetching board list from micropython.org")
        raise SystemExit(1)
    except httpx.ConnectError as exc:
        output.error(f"connection failed fetching board list: {exc}")
        raise SystemExit(1)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        output.error(f"failed to fetch board list: HTTP {exc.response.status_code}")
        raise SystemExit(1)

    parser = _BoardLinkParser()
    parser.feed(response.text)

    seen: set[str] = set()
    boards: list[BoardInfo] = []
    for board_id, name in parser.boards:
        if board_id not in seen:
            seen.add(board_id)
            boards.append(BoardInfo(id=board_id, name=name or board_id))
    return boards


def _load_board_list(path: Path) -> list[BoardInfo]:
    """Load board list from the JSON cache."""
    data = json.loads(path.read_text())
    return [BoardInfo(**b) for b in data["boards"]]


def _save_board_list(path: Path, boards: list[BoardInfo]) -> None:
    """Save board list to the JSON cache."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "fetched_at": time.time(),
        "boards": [{"id": b.id, "name": b.name} for b in boards],
    }
    try:
        path.write_text(json.dumps(data, indent=2))
    except OSError as exc:
        output.warn(f"could not cache board list: {exc}")


def fetch_board_list(*, force_refresh: bool = False) -> list[BoardInfo]:
    """Return all available boards, using cache when fresh."""
    path = _board_list_path()
    return _cached_fetch(
        path,
        scrape_fn=_scrape_board_list,
        load_fn=_load_board_list,
        save_fn=_save_board_list,
        label="board list",
        force_refresh=force_refresh,
    )
