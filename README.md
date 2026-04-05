# brasa

MicroPython developer tools. Flash, deploy, watch, monitor.

## Install

```
pip install brasa
```

## Commands

```
brasa dev            # deploy, watch for changes, stream serial
brasa deploy         # compile & push src/ to device
brasa firmware       # manage firmware (list, download, install, select, show)
brasa serial         # read-only serial monitor
brasa repl           # interactive REPL
brasa diff           # diff local src/ vs device files
brasa detect         # show connected device port
brasa exec "expr"    # run expression on device
brasa restart        # reboot device
```

All commands auto-detect the serial port. Override with `--port /dev/cu.xxx`.

### Firmware management

```
brasa firmware list [BOARD]          # list available versions for a board
brasa firmware download              # download firmware to local cache
brasa firmware install               # download + flash + save to config
brasa firmware install --from-config # install the version pinned in config
brasa firmware select                # pick a version and save to config (no flash)
brasa firmware show                  # show firmware version on connected device
```

Board, variant, and version can be passed as flags (`--board`, `--variant`, `--version`) or selected interactively. When a device is connected, the board is auto-detected. Values already in config are used as defaults.

> **Note:** `brasa flash` is deprecated in favor of `brasa firmware install --from-config`.

## Configuration

Create a `brasa.toml` in your project root (or add `[tool.brasa.*]` sections to `pyproject.toml`):

```toml
[firmware]
board = "ESP8266_GENERIC"
variant = ""
version = "1.27.0"
date = "20251209"

[deploy]
src = "src"
env_file = ".env"
boot_files = ["boot.py", "main.py"]
romfs = true
mpy_compile = true

[serial]
baud_rate = 115200

[port]
patterns = ["/dev/cu.usbserial*", "/dev/cu.wchusbserial*", "/dev/cu.SLAB_USBtoUART*"]
```

Commands that don't need config (`detect`, `serial`, `repl`, `restart`, `exec`) work without it. Commands that do (`flash`, `deploy`, `dev`, `diff`) will error if no config is found.

All fields have defaults — a minimal config works:

```toml
[firmware]
version = "1.27.0"
date = "20251209"
```

## Workflow

```bash
brasa firmware install   # flash firmware (first time or update)
brasa dev                # deploy + watch + serial monitor (daily development)
brasa diff               # check what's different on device (ROMFS-aware)
```

## Why

Every MicroPython project re-invents the same Makefile: detect the serial port, lock it, flash firmware, deploy files, watch for changes, read serial output. Brasa replaces that with a single CLI that works across projects.

## Requirements

- Python 3.12+
- macOS or Linux
