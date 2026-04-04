"""Deploy project files to a MicroPython device."""

import shutil
import tempfile
from pathlib import Path

from brasa.core.config import DeployConfig
from brasa.core.device import fs_cp, mpremote_run
from brasa.core.output import error, status


def _excluded_filenames(cfg: DeployConfig) -> set[str]:
    """Return bare filenames that should be excluded from source deploys."""
    return {Path(name).name for name in cfg.boot_files} | {Path(cfg.env_file).name}


def deploy(port: str, cfg: DeployConfig) -> None:
    """Deploy project files to the device. Caller must hold the port lock."""
    _copy_boot_files(port, cfg)
    if cfg.romfs:
        _deploy_romfs(port, cfg)
    else:
        _deploy_flat(port, cfg)


def _copy_boot_files(port: str, cfg: DeployConfig) -> None:
    """Copy env_file and boot_files to the device root."""
    env_path = Path(cfg.env_file)
    if not env_path.is_file():
        error(f"env file not found: {cfg.env_file}")
        raise SystemExit(1)

    status("deploy", f"copying {cfg.env_file}")
    fs_cp(port, cfg.env_file, ":/")

    for boot_file in cfg.boot_files:
        path = Path(boot_file)
        if not path.is_file():
            path = Path(cfg.src) / boot_file
        if path.is_file():
            status("deploy", f"copying {path}")
            fs_cp(port, str(path), ":/")


def _deploy_romfs(port: str, cfg: DeployConfig) -> None:
    """Deploy source files via mpremote romfs (with optional mpy compilation)."""
    src_dir = Path(cfg.src)
    tmpdir = tempfile.mkdtemp(prefix="brasa-deploy-")

    try:
        exclude = _excluded_filenames(cfg)
        for py_file in src_dir.rglob("*.py"):
            if py_file.name in exclude:
                continue
            # Preserve directory structure relative to src.
            rel = py_file.relative_to(src_dir)
            dest = Path(tmpdir) / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(py_file, dest)

        status("deploy", f"deploying via romfs from {cfg.src}/")
        args: list[str] = ["romfs"]
        if cfg.mpy_compile:
            args.append("--mpy")
        args.extend(["deploy", tmpdir + "/"])
        mpremote_run(port, *args)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _deploy_flat(port: str, cfg: DeployConfig) -> None:
    """Copy all source files to the device root (no romfs)."""
    src_dir = Path(cfg.src)
    exclude = _excluded_filenames(cfg)

    for src_file in src_dir.rglob("*"):
        if not src_file.is_file():
            continue
        if src_file.name in exclude:
            continue
        status("deploy", f"copying {src_file}")
        fs_cp(port, str(src_file), ":/")
