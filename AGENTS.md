# AGENTS.md — brasa

## What this is

CLI tool that replaces the bespoke Makefile + scripts every MicroPython project ends up writing. Handles the full developer cycle: detect serial ports, lock them, flash firmware, deploy code, watch for changes, read serial output, diff local vs device, and run expressions.

## Architecture

- **CLI framework**: Typer (Click-based, type-hint driven). Entry point: `src/brasa/cli.py`
- **`src/brasa/commands/`**: One module per CLI command (`detect`, `serial`, `repl`, `flash`, `deploy`, `dev`, `diff`, `exec`, `restart`) plus the `firmware` subcommand group (`list`, `download`, `install`, `select`, `show`)
- **`src/brasa/core/`**: Domain logic — port detection, serial port locking (`fcntl.flock`), serial reader, device operations, firmware index & download, TOML config writer, terminal output helpers
- **Config**: `brasa.toml` in consumer project root (or `[tool.brasa.*]` in their `pyproject.toml`). Config write-back (e.g. `firmware select`) resolves to the existing config file, defaulting to `pyproject.toml`.

## Build & run

```bash
uv sync                        # install deps
uv run brasa                   # run CLI
uv run pytest                  # run tests
uv run ruff check src/         # lint
uv run ruff format src/        # format
uv run ty check src/           # type check

# Or use Make targets:
make check                     # lint + typecheck + test
make lint / make format        # ruff
make typecheck                 # ty
make test / make test-cov      # pytest
```

## Code style

- Type hints on all function signatures and return types
- DDD / hexagonal architecture: commands depend on core, never the reverse
- SOLID principles — single-responsibility modules, depend on abstractions
- All imports at top level of the file
- Keep `__init__.py` files empty unless they need content

## Key constraints

- **No async.** The reference implementation (neo-redstone) uses threads for serial reading alongside synchronous mpremote calls. Keep that model.
- **Don't fully abstract mpremote.** Use it for REPL, fs operations, ROMFS deploy, reset. Only bypass it for serial reading (pyserial is better for passive monitoring).
- **Serial port locking is built in.** Every command that touches the serial port acquires an `fcntl.flock` lock automatically. Reentrant via `BRASA_PORT_LOCKED` env var to prevent deadlocks (e.g., `dev` calling `deploy`).
- **One serial reader.** Shared by `serial` and `dev` commands, parameterized for pause/stop/filter behavior.
- **macOS and Linux only.** Port detection uses `/dev/cu.*` patterns. No Windows support yet.

## Testing

- pytest with `@pytest.mark.hardware` for tests that need a physical device
- Mock mpremote subprocess calls via `pytest-subprocess`
- Unit test core utilities (port detection, lock logic, serial reader) with mocks
- Integration test bed: neo-redstone project (install brasa as dev dep, replace Makefile targets)
