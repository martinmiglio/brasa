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
brasa flash          # download firmware + flash device
brasa serial         # read-only serial monitor
brasa repl           # interactive REPL
brasa diff           # diff local src/ vs device files
brasa detect         # show connected device port
brasa exec "expr"    # run expression on device
brasa restart        # reboot device
```

All commands auto-detect the serial port. Override with `--port /dev/cu.xxx`.

## Configuration

Create a `brasa.toml` in your project root (or add `[tool.brasa]` to `pyproject.toml`):

```toml
[firmware]
board = "ESP8266"
variant = "GENERIC-FLASH_2M_ROMFS"
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
brasa flash          # flash firmware (first time or update)
brasa dev            # deploy + watch + serial monitor (daily development)
brasa diff           # check what's different on device
```

## Why

Every MicroPython project re-invents the same Makefile: detect the serial port, lock it, flash firmware, deploy files, watch for changes, read serial output. Brasa replaces that with a single CLI that works across projects.

## Requirements

- Python 3.12+
- macOS or Linux
