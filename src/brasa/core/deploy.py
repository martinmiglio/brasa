"""Deploy project files to a MicroPython device."""

import shutil
import subprocess
import tempfile
from pathlib import Path

from brasa.core.config import DeployConfig
from brasa.core.device import fs_cp, mpremote_run
from brasa.core.output import error, status


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

    try:
        status("deploy", f"copying {cfg.env_file}")
        fs_cp(port, cfg.env_file, ":/")
    except subprocess.CalledProcessError as exc:
        error(f"failed to copy {cfg.env_file}: {exc.stderr or exc}")
        raise SystemExit(1)

    for boot_file in cfg.boot_files:
        path = Path(boot_file)
        if not path.is_file():
            path = Path(cfg.src) / boot_file
        if path.is_file():
            try:
                status("deploy", f"copying {path}")
                fs_cp(port, str(path), ":/")
            except subprocess.CalledProcessError as exc:
                error(f"failed to copy {path}: {exc.stderr or exc}")
                raise SystemExit(1)


def _deploy_romfs(port: str, cfg: DeployConfig) -> None:
    """Deploy source files via mpremote romfs (with optional mpy compilation)."""
    src_dir = Path(cfg.src)
    tmpdir = tempfile.mkdtemp(prefix="brasa-deploy-")

    try:
        exclude = cfg.excluded_filenames
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
            if shutil.which("mpy-cross") is None:
                error(
                    "mpy-cross is required when mpy_compile is enabled but was not found on PATH. "
                    "Install it with `uv add mpy-cross` or set mpy_compile = false in brasa.toml"
                )
                raise SystemExit(1)
            args.append("--mpy")
        args.extend(["deploy", tmpdir + "/"])
        try:
            mpremote_run(port, *args)
        except subprocess.CalledProcessError as exc:
            error(f"romfs deploy failed: {exc.stderr or exc}")
            raise SystemExit(1)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _deploy_flat(port: str, cfg: DeployConfig) -> None:
    """Copy all source files to the device root (no romfs)."""
    src_dir = Path(cfg.src)
    exclude = cfg.excluded_filenames

    for src_file in src_dir.rglob("*"):
        if not src_file.is_file():
            continue
        if src_file.name in exclude:
            continue
        try:
            status("deploy", f"copying {src_file}")
            fs_cp(port, str(src_file), ":/")
        except subprocess.CalledProcessError as exc:
            error(f"failed to copy {src_file}: {exc.stderr or exc}")
            raise SystemExit(1)
