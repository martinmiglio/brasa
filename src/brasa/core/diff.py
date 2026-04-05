"""Diff logic — compare local source files against device files."""

import difflib
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from brasa.core.config import DeployConfig
from brasa.core.device import fs_cat, fs_ls
from brasa.core.output import cyan, dim, error, green, red, success


class DiffStatus(Enum):
    MODIFIED = "modified"
    LOCAL_ONLY = "local_only"
    DEVICE_ONLY = "device_only"
    ROMFS = "romfs"


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


def _diff_text_files(
    port: str,
    cfg: DeployConfig,
    src_dir: Path,
    local_files: set[str],
    device_files: set[str],
) -> list[FileDiff]:
    """Compare files present on both local and device, returning diffs for modified ones."""
    diffs: list[FileDiff] = []
    for name in sorted(local_files & device_files):
        local_content = (src_dir / name).read_text()
        try:
            device_content = fs_cat(port, f"/{name}")
        except subprocess.CalledProcessError:
            error(f"could not read /{name} from device")
            continue
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
    return diffs


def _diff_flat(
    port: str, cfg: DeployConfig, src_dir: Path, local_files: set[str]
) -> list[FileDiff]:
    """Flat (non-ROMFS) diff: compare all local .py against device root .py files."""
    try:
        listing = fs_ls(port, "/")
    except subprocess.CalledProcessError:
        error("could not list files on device — is the board connected?")
        raise SystemExit(1)
    device_files = {
        name for name in _parse_device_filenames(listing) if name.endswith(".py")
    }

    diffs = _diff_text_files(port, cfg, src_dir, local_files, device_files)

    for name in sorted(local_files - device_files):
        diffs.append(FileDiff(path=name, status=DiffStatus.LOCAL_ONLY, diff_lines=[]))

    for name in sorted(device_files - local_files):
        diffs.append(FileDiff(path=name, status=DiffStatus.DEVICE_ONLY, diff_lines=[]))

    return diffs


def _diff_romfs(
    port: str, cfg: DeployConfig, src_dir: Path, local_files: set[str]
) -> list[FileDiff]:
    """ROMFS-aware diff: boot files diffed at root, others checked against /rom/."""
    boot_names = {Path(b).name for b in cfg.boot_files}
    env_name = Path(cfg.env_file).name
    local_boot = local_files & boot_names
    local_romfs = local_files - boot_names - {env_name}

    # Get device root listing for boot file comparison.
    try:
        root_listing = fs_ls(port, "/")
    except subprocess.CalledProcessError:
        error("could not list files on device — is the board connected?")
        raise SystemExit(1)
    root_py_files = {
        name for name in _parse_device_filenames(root_listing) if name.endswith(".py")
    }

    diffs: list[FileDiff] = []

    # Text-diff boot files against device root.
    diffs.extend(_diff_text_files(port, cfg, src_dir, local_boot, root_py_files))

    # Boot files only local.
    for name in sorted(local_boot - root_py_files):
        diffs.append(FileDiff(path=name, status=DiffStatus.LOCAL_ONLY, diff_lines=[]))

    # Stale .py at root that aren't boot files (leftover from previous flat deploy).
    stale_root = root_py_files - boot_names
    for name in sorted(stale_root):
        diffs.append(FileDiff(path=name, status=DiffStatus.DEVICE_ONLY, diff_lines=[]))

    # Check /rom/ for .mpy files.
    try:
        rom_listing = fs_ls(port, "/rom/")
        rom_mpy_names = {
            name
            for name in _parse_device_filenames(rom_listing)
            if name.endswith(".mpy")
        }
    except subprocess.CalledProcessError:
        rom_mpy_names = set()

    # Convert .mpy names to .py for matching.
    rom_py_from_mpy = {name.removesuffix(".mpy") + ".py" for name in rom_mpy_names}

    # Files in both local_romfs and device rom -> ROMFS.
    for name in sorted(local_romfs & rom_py_from_mpy):
        diffs.append(FileDiff(path=name, status=DiffStatus.ROMFS, diff_lines=[]))

    # Files only in local_romfs -> LOCAL_ONLY.
    for name in sorted(local_romfs - rom_py_from_mpy):
        diffs.append(FileDiff(path=name, status=DiffStatus.LOCAL_ONLY, diff_lines=[]))

    # .mpy files only on device -> DEVICE_ONLY (use the .mpy name).
    device_only_mpy = rom_mpy_names - {
        name.removesuffix(".py") + ".mpy" for name in local_romfs
    }
    for name in sorted(device_only_mpy):
        diffs.append(FileDiff(path=name, status=DiffStatus.DEVICE_ONLY, diff_lines=[]))

    return diffs


def diff_files(port: str, cfg: DeployConfig) -> list[FileDiff]:
    """Compare local src/*.py files with device files. Skip .env."""
    src_dir = Path(cfg.src)
    local_files: set[str] = set()
    if src_dir.is_dir():
        local_files = {p.name for p in src_dir.glob("*.py")}

    if cfg.romfs:
        return _diff_romfs(port, cfg, src_dir, local_files)
    return _diff_flat(port, cfg, src_dir, local_files)


def print_diff(diffs: list[FileDiff]) -> None:
    """Print colored diff output to stderr."""
    if not diffs:
        success("Device is up to date")
        return

    modified = 0
    local_only = 0
    device_only = 0
    romfs = 0

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
        elif fd.status == DiffStatus.ROMFS:
            romfs += 1
            print(dim(f"Deployed (romfs): {fd.path}"), file=sys.stderr)

    parts: list[str] = []
    if modified:
        parts.append(f"{modified} modified")
    if local_only:
        parts.append(f"{local_only} local only")
    if device_only:
        parts.append(f"{device_only} device only")
    if romfs:
        parts.append(f"{romfs} romfs")
    print(dim(f"\n{', '.join(parts)}"), file=sys.stderr)
