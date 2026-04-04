# brasa

MicroPython developer tools. Flash, deploy, watch, monitor.

```
pip install brasa
```

```
brasa flash          # download firmware + flash device
brasa deploy         # compile & push src/ to device
brasa dev            # deploy + watch for changes
brasa serial         # read-only serial monitor
brasa repl           # interactive REPL
brasa detect         # show connected device port
brasa diff           # diff local src/ vs device
brasa exec "expr"    # run expression on device
brasa restart        # reboot device
```

## Why

Every MicroPython project re-invents the same Makefile: detect the serial port, lock it, flash firmware, deploy files, watch for changes, read serial output. Brasa replaces that with a single CLI that works across projects.

## Status

Early development. See [HANDOFF.md](HANDOFF.md) for architecture and roadmap.
