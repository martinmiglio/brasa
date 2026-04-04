"""Firmware index — scrape micropython.org for available firmware and cache locally."""

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
