"""Diff logic — compare local source files against device files."""

import difflib
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from brasa.core.config import DeployConfig
from brasa.core.device import fs_cat, fs_ls
from brasa.core.output import cyan, dim, green, red, success


class DiffStatus(Enum):
    MODIFIED = "modified"
    LOCAL_ONLY = "local_only"
    DEVICE_ONLY = "device_only"


@dataclass
class FileDiff:
    path: str
    status: DiffStatus
    diff_lines: list[str]  # unified diff lines, empty for non-modified


def _parse_device_filenames(listing: str) -> set[str]:
    """Extract filenames from fs_ls output (lines like '       123 boot.py')."""
    names: set[str] = set()
    for line in listing.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(None, 1)
        if len(parts) == 2:
            names.add(parts[1])
    return names


def diff_files(port: str, cfg: DeployConfig) -> list[FileDiff]:
    """Compare local src/*.py files with device files. Skip .env."""
    src_dir = Path(cfg.src)
    local_files: set[str] = set()
    if src_dir.is_dir():
        local_files = {p.name for p in src_dir.glob("*.py")}

    listing = fs_ls(port, "/")
    device_files = {
        name for name in _parse_device_filenames(listing) if name.endswith(".py")
    }

    diffs: list[FileDiff] = []

    # Files present on both sides.
    for name in sorted(local_files & device_files):
        local_content = (src_dir / name).read_text()
        device_content = fs_cat(port, f"/{name}")
        if local_content == device_content:
            continue
        diff_lines = list(
            difflib.unified_diff(
                device_content.splitlines(keepends=True),
                local_content.splitlines(keepends=True),
                fromfile=f"device:/{name}",
                tofile=f"local:{cfg.src}/{name}",
            )
        )
        diffs.append(
            FileDiff(path=name, status=DiffStatus.MODIFIED, diff_lines=diff_lines)
        )

    # Local-only files.
    for name in sorted(local_files - device_files):
        diffs.append(FileDiff(path=name, status=DiffStatus.LOCAL_ONLY, diff_lines=[]))

    # Device-only files.
    for name in sorted(device_files - local_files):
        diffs.append(FileDiff(path=name, status=DiffStatus.DEVICE_ONLY, diff_lines=[]))

    return diffs


def print_diff(diffs: list[FileDiff]) -> None:
    """Print colored diff output to stderr."""
    if not diffs:
        success("Device is up to date")
        return

    modified = 0
    local_only = 0
    device_only = 0

    for fd in diffs:
        if fd.status == DiffStatus.MODIFIED:
            modified += 1
            for line in fd.diff_lines:
                text = line.rstrip("\n")
                if text.startswith("---") or text.startswith("+++"):
                    print(cyan(text), file=sys.stderr)
                elif text.startswith("@@"):
                    print(cyan(text), file=sys.stderr)
                elif text.startswith("-"):
                    print(red(text), file=sys.stderr)
                elif text.startswith("+"):
                    print(green(text), file=sys.stderr)
                else:
                    print(dim(text), file=sys.stderr)
        elif fd.status == DiffStatus.LOCAL_ONLY:
            local_only += 1
            print(green(f"Only local: {fd.path}"), file=sys.stderr)
        elif fd.status == DiffStatus.DEVICE_ONLY:
            device_only += 1
            print(red(f"Only on device: {fd.path}"), file=sys.stderr)

    parts: list[str] = []
    if modified:
        parts.append(f"{modified} modified")
    if local_only:
        parts.append(f"{local_only} local only")
    if device_only:
        parts.append(f"{device_only} device only")
    print(dim(f"\n{', '.join(parts)}"), file=sys.stderr)
