"""firmware command group — discover, download, install, and pin MicroPython firmware."""

import typer

from brasa.core import output
from brasa.core.config import require_config
from brasa.core.firmware import (
    download_entry,
    install_firmware,
    platform_for_board,
)
from brasa.core.firmware_index import (
    BoardIndex,
    FirmwareEntry,
    fetch_board_index,
    find_entry,
    list_variants,
    list_versions,
)
from brasa.core.lock import port_lock
from brasa.core.port import resolve_port
from brasa.core.toml_writer import pin_firmware as write_pin

firmware_app = typer.Typer(
    name="firmware",
    help="Manage MicroPython firmware — list, download, install, pin.",
    no_args_is_help=True,
)


def _prompt_board() -> str:
    """Interactively prompt for a board name."""
    import questionary

    board = questionary.text("Board identifier (e.g. ESP32_GENERIC, RPI_PICO):").ask()
    if not board:
        output.error("no board specified")
        raise SystemExit(1)
    return board.strip()


def _prompt_variant(index: BoardIndex) -> str:
    """Interactively prompt to select a variant."""
    import questionary

    variants = list_variants(index)
    if len(variants) == 1:
        return variants[0]
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


def _resolve_entry(
    board: str | None,
    variant: str | None,
    version: str | None,
    *,
    from_config: bool = False,
    refresh: bool = False,
) -> FirmwareEntry:
    """Resolve a FirmwareEntry from flags, config, or interactive prompts."""
    if from_config:
        cfg = require_config()
        fw = cfg.firmware
        if not fw.version:
            output.error("firmware.version is required in config for --from-config")
            raise SystemExit(1)
        index = fetch_board_index(fw.board, force_refresh=refresh)
        # Try to find by board+variant+version in index
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

    if board is None:
        board = _prompt_board()

    index = fetch_board_index(board, force_refresh=refresh)

    if variant is None:
        variant = _prompt_variant(index)

    if version is None:
        version = _prompt_version(index, variant)

    entry = find_entry(index, variant, version)
    if entry is None:
        output.error(
            f"no firmware found for {board} variant={variant!r} version={version}"
        )
        raise SystemExit(1)
    return entry


@firmware_app.command("list")
def list_cmd(
    board: str = typer.Option(..., "--board", "-b", help="Board identifier"),
    refresh: bool = typer.Option(False, "--refresh", help="Force refresh cached index"),
    preview: bool = typer.Option(False, "--preview", help="Include preview builds"),
) -> None:
    """List available firmware versions for a board."""
    index = fetch_board_index(board, force_refresh=refresh)
    variants = list_variants(index)

    if not variants:
        output.warn(f"no firmware found for {board}")
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
    """Download and install firmware onto the device."""
    entry = _resolve_entry(board, variant, version, from_config=from_config)
    firmware_path = download_entry(entry)
    platform = platform_for_board(entry.board)

    if platform == "uf2":
        install_firmware(firmware_path, platform="uf2")
    else:
        port_flag = ctx.obj.get("port") if ctx.obj else None
        port = resolve_port(port_flag)
        with port_lock(port, "firmware install"):
            install_firmware(firmware_path, port=port, platform="esp")

    output.success("firmware installed")


@firmware_app.command()
def pin(
    board: str | None = typer.Option(None, "--board", "-b", help="Board identifier"),
    variant: str | None = typer.Option(None, "--variant", help="Board variant"),
    version: str | None = typer.Option(None, "--version", help="Firmware version"),
) -> None:
    """Pin a firmware version in brasa.toml."""
    entry = _resolve_entry(board, variant, version)
    path = write_pin(entry.board, entry.variant, entry.version, entry.date)
    output.success(f"firmware pinned in {path}")
