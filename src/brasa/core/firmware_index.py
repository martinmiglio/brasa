"""Firmware index — scrape micropython.org for available firmware and cache locally."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path

import httpx

from brasa.core import output

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
        # Deferred import to break circular dependency (firmware imports firmware_index)
        from brasa.core.firmware import _firmware_ext

        ext = _firmware_ext(board)
        variant_part = f"-{variant}" if variant else ""
        filename = f"{board}{variant_part}-{date}-v{version}.{ext}"
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


class _FirmwareLinkParser(HTMLParser):
    """Extract firmware download hrefs from a micropython.org board page."""

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value and "/resources/firmware/" in value:
                self.hrefs.append(value)


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
    response = httpx.get(url, follow_redirects=True)
    if response.status_code == 404:
        output.error(
            f"board '{board}' not found on micropython.org — "
            "run 'brasa firmware list' with a valid board identifier "
            "(e.g. ESP8266_GENERIC, ESP32_GENERIC, RPI_PICO)"
        )
        raise SystemExit(1)
    response.raise_for_status()

    parser = _FirmwareLinkParser()
    parser.feed(response.text)

    entries: list[FirmwareEntry] = []
    seen: set[str] = set()
    for href in parser.hrefs:
        entry = _parse_firmware_href(href, board)
        if entry and entry.filename not in seen:
            seen.add(entry.filename)
            entries.append(entry)
    return entries


def _save_index(board: str, entries: list[FirmwareEntry]) -> BoardIndex:
    """Save a board index to the JSON cache."""
    now = time.time()
    index = BoardIndex(board=board, entries=tuple(entries), fetched_at=now)
    path = _index_path(board)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "board": board,
        "fetched_at": now,
        "entries": [asdict(e) for e in entries],
    }
    path.write_text(json.dumps(data, indent=2))
    return index


def _load_index(board: str) -> BoardIndex:
    """Load a board index from the JSON cache."""
    path = _index_path(board)
    data = json.loads(path.read_text())
    entries = tuple(FirmwareEntry(**e) for e in data["entries"])
    return BoardIndex(
        board=data["board"], entries=entries, fetched_at=data["fetched_at"]
    )


def fetch_board_index(board: str, *, force_refresh: bool = False) -> BoardIndex:
    """Return firmware entries for a board, using cache when fresh."""
    path = _index_path(board)
    if not force_refresh and _is_fresh(path):
        output.status("firmware", f"using cached index for {board}")
        return _load_index(board)
    entries = _scrape_board_page(board)
    return _save_index(board, entries)


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
    response = httpx.get(url, follow_redirects=True)
    response.raise_for_status()

    parser = _BoardLinkParser()
    parser.feed(response.text)

    seen: set[str] = set()
    boards: list[BoardInfo] = []
    for board_id, name in parser.boards:
        if board_id not in seen:
            seen.add(board_id)
            boards.append(BoardInfo(id=board_id, name=name or board_id))
    return boards


def fetch_board_list(*, force_refresh: bool = False) -> list[BoardInfo]:
    """Return all available boards, using cache when fresh."""
    path = _board_list_path()
    if not force_refresh and _is_fresh(path):
        output.status("firmware", "using cached board list")
        data = json.loads(path.read_text())
        return [BoardInfo(**b) for b in data["boards"]]

    boards = _scrape_board_list()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "fetched_at": time.time(),
        "boards": [{"id": b.id, "name": b.name} for b in boards],
    }
    path.write_text(json.dumps(data, indent=2))
    return boards
