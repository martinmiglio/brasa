"""firmware command group — discover, download, install, and select MicroPython firmware."""

import sys
from typing import Annotated

import typer

from brasa.core import output
from brasa.core.config import load_config, require_config
from brasa.core.device import detect_board
from brasa.core.firmware import (
    download_entry,
    install_firmware,
    platform_for_board,
)
from brasa.core.firmware_index import (
    BoardIndex,
    FirmwareEntry,
    fetch_board_index,
    fetch_board_list,
    find_entry,
    list_variants,
    list_versions,
)
from brasa.core.lock import port_lock
from brasa.core.port import resolve_port
from brasa.core.toml_writer import pin_firmware as write_pin

firmware_app = typer.Typer(
    name="firmware",
    help="Manage MicroPython firmware — list, download, install, select.",
    no_args_is_help=True,
)


def _is_interactive() -> bool:
    """Check if stdin is a real terminal (not piped/redirected)."""
    return sys.stdin.isatty()


# ── Board resolution ───────────────────────────────────────────────────────


def _resolve_board(
    board: str | None, *, port: str | None = None, use_config: bool = True
) -> str:
    """Resolve board from flag → config → device → interactive prompt."""
    if board:
        return board

    if use_config:
        cfg = load_config()
        if cfg.firmware.board and cfg.firmware.version:
            output.status("firmware", f"using board from config: {cfg.firmware.board}")
            return cfg.firmware.board

    # Device auto-detect (best-effort)
    try:
        resolved_port = resolve_port(port)
        detected = detect_board(resolved_port)
        if detected:
            if not _is_interactive():
                return detected
            import questionary

            if questionary.confirm(
                f"Detected {detected} from device. Use it?", default=True
            ).ask():
                return detected
    except (SystemExit, OSError):
        pass

    # Interactive: fuzzy-searchable board list
    import questionary

    boards = fetch_board_list()
    board_ids = [b.id for b in boards]
    meta = {b.id: b.name for b in boards}
    selected = questionary.autocomplete(
        "Board:",
        choices=board_ids,
        meta_information=meta,
    ).ask()
    if not selected or selected not in board_ids:
        output.error("no board selected")
        raise SystemExit(1)
    return selected


# ── Variant / version prompts ──────────────────────────────────────────────


def _prompt_variant(index: BoardIndex) -> str:
    """Interactively prompt to select a variant."""
    import questionary

    variants = list_variants(index)
    if len(variants) == 1:
        chosen = variants[0]
        label = chosen if chosen else "(default)"
        output.status("firmware", f"auto-selected variant: {label}")
        return chosen
    labels = [v if v else "(default)" for v in variants]
    choice = questionary.select("Variant:", choices=labels).ask()
    if choice is None:
        raise SystemExit(1)
    return "" if choice == "(default)" else choice


def _prompt_version(index: BoardIndex, variant: str) -> str:
    """Interactively prompt to select a version."""
    import questionary

    versions = list_versions(index, variant)
    if not versions:
        output.error(f"no stable versions found for variant '{variant}'")
        raise SystemExit(1)
    choice = questionary.select("Version:", choices=versions).ask()
    if choice is None:
        raise SystemExit(1)
    return choice


# ── Entry resolution ───────────────────────────────────────────────────────


def _resolve_entry(
    board: str | None,
    variant: str | None,
    version: str | None,
    *,
    from_config: bool = False,
    use_config: bool = True,
    refresh: bool = False,
    port: str | None = None,
) -> FirmwareEntry:
    """Resolve a FirmwareEntry from flags, config, or interactive prompts."""
    if from_config:
        cfg = require_config()
        fw = cfg.firmware
        if not fw.version:
            output.error("firmware.version is required in config for --from-config")
            raise SystemExit(1)
        index = fetch_board_index(fw.board, force_refresh=refresh)
        entry = find_entry(index, fw.variant, fw.version)
        if entry:
            return entry
        # Fall back: construct entry from config (may not be in index for older versions)
        filename_variant = f"-{fw.variant}" if fw.variant else ""
        ext = "uf2" if platform_for_board(fw.board) == "uf2" else "bin"
        filename = f"{fw.board}{filename_variant}-{fw.date}-v{fw.version}.{ext}"
        return FirmwareEntry(
            board=fw.board,
            variant=fw.variant,
            version=fw.version,
            date=fw.date,
            filename=filename,
            url=f"https://micropython.org/resources/firmware/{filename}",
            ext=ext,
        )

    resolved_board = _resolve_board(board, port=port, use_config=use_config)

    # Fill variant/version from config if not given via CLI flags
    if use_config and (variant is None or version is None):
        cfg = load_config()
        if cfg.firmware.board == resolved_board:
            if variant is None and cfg.firmware.variant:
                variant = cfg.firmware.variant
                output.status("firmware", f"using variant from config: {variant}")
            if version is None and cfg.firmware.version:
                version = cfg.firmware.version
                output.status("firmware", f"using version from config: {version}")

    index = fetch_board_index(resolved_board, force_refresh=refresh)

    if variant is None:
        variant = _prompt_variant(index)

    if version is None:
        version = _prompt_version(index, variant)

    entry = find_entry(index, variant, version)
    if entry is None:
        output.error(
            f"no firmware found for {resolved_board} variant={variant!r} version={version}"
        )
        raise SystemExit(1)
    return entry


# ── Commands ───────────────────────────────────────────────────────────────


@firmware_app.command("list")
def list_cmd(
    board: Annotated[str | None, typer.Argument(help="Board identifier")] = None,
    refresh: bool = typer.Option(False, "--refresh", help="Force refresh cached index"),
    preview: bool = typer.Option(False, "--preview", help="Include preview builds"),
) -> None:
    """List available firmware versions for a board."""
    resolved_board = _resolve_board(board)
    index = fetch_board_index(resolved_board, force_refresh=refresh)
    variants = list_variants(index)

    if not variants:
        output.warn(f"no firmware found for {resolved_board}")
        return

    for variant in variants:
        label = variant if variant else "(default)"
        versions = list_versions(index, variant, include_preview=preview)
        if not versions:
            continue
        output.status("variant", label)
        for v in versions:
            output.print_stdout(f"  {v}")


@firmware_app.command()
def download(
    board: str | None = typer.Option(None, "--board", "-b", help="Board identifier"),
    variant: str | None = typer.Option(None, "--variant", help="Board variant"),
    version: str | None = typer.Option(None, "--version", help="Firmware version"),
    from_config: bool = typer.Option(
        False, "--from-config", help="Use brasa.toml settings"
    ),
) -> None:
    """Download firmware to the local cache."""
    entry = _resolve_entry(board, variant, version, from_config=from_config)
    path = download_entry(entry)
    output.success(f"firmware ready: {path}")


@firmware_app.command()
def install(
    ctx: typer.Context,
    board: str | None = typer.Option(None, "--board", "-b", help="Board identifier"),
    variant: str | None = typer.Option(None, "--variant", help="Board variant"),
    version: str | None = typer.Option(None, "--version", help="Firmware version"),
    from_config: bool = typer.Option(
        False, "--from-config", help="Use brasa.toml settings"
    ),
) -> None:
    """Download and install firmware onto the device, then save to config."""
    port_flag = ctx.obj.get("port") if ctx.obj else None
    entry = _resolve_entry(
        board, variant, version, from_config=from_config, port=port_flag
    )
    firmware_path = download_entry(entry)
    platform = platform_for_board(entry.board)

    if platform == "uf2":
        install_firmware(firmware_path, platform="uf2")
    else:
        port = resolve_port(port_flag)
        with port_lock(port, "firmware install"):
            install_firmware(firmware_path, port=port, platform="esp")

    write_pin(entry.board, entry.variant, entry.version, entry.date)
    output.success("firmware installed and saved to brasa.toml")


@firmware_app.command()
def select(
    board: str | None = typer.Option(None, "--board", "-b", help="Board identifier"),
    variant: str | None = typer.Option(None, "--variant", help="Board variant"),
    version: str | None = typer.Option(None, "--version", help="Firmware version"),
) -> None:
    """Select a firmware version and save to brasa.toml (no flash)."""
    entry = _resolve_entry(board, variant, version, use_config=False)
    path = write_pin(entry.board, entry.variant, entry.version, entry.date)
    output.success(f"firmware saved to {path}")
