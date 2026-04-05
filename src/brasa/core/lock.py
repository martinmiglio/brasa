"""Exclusive advisory lock on a serial port via fcntl.flock."""

import fcntl
import json
import os
import tempfile
import time
from collections.abc import Generator, Sequence
from contextlib import contextmanager

from brasa.core.output import error, status, warn
from brasa.core.port import resolve_port

_ENV_KEY = "BRASA_PORT_LOCKED"
_LOCK_DIR = tempfile.gettempdir()


def _lock_path(port: str) -> str:
    """Return the lock file path for *port*."""
    return os.path.join(_LOCK_DIR, f"brasa-{os.path.basename(port)}.lock")


@contextmanager
def port_lock(port: str, caller: str) -> Generator[None, None, None]:
    """Acquire an exclusive advisory lock on *port*.

    If the environment variable ``BRASA_PORT_LOCKED`` already equals *port*,
    the lock is assumed to be held by an outer command and acquisition is
    skipped (reentrant).
    """
    # Reentrant — an outer command already holds the lock.
    if os.environ.get(_ENV_KEY) == port:
        yield
        return

    path = _lock_path(port)
    fd: int | None = None
    prev_env = os.environ.get(_ENV_KEY)

    try:
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)

        # Try non-blocking first.
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Another process holds the lock — show who.
            try:
                data = json.loads(os.pread(fd, 4096, 0).decode())
                holder = data.get("caller", "unknown")
                pid = data.get("pid", "?")
                warn(f"port {port} locked by '{holder}' (pid {pid}), waiting…")
            except (json.JSONDecodeError, OSError):
                warn(f"port {port} locked by another process, waiting…")

            # Retry with timeout instead of blocking indefinitely.
            deadline = time.monotonic() + 30.0
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        error(f"timed out waiting for port lock on {port}")
                        raise SystemExit(1)
                    time.sleep(0.5)

        # Write metadata so other waiters can report who holds the lock.
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        meta = json.dumps({"pid": os.getpid(), "caller": caller})
        os.write(fd, meta.encode())

        os.environ[_ENV_KEY] = port
        status("lock", f"{port} acquired by '{caller}'")

        yield

    except KeyboardInterrupt:
        raise SystemExit(130)

    finally:
        # Restore env.
        if prev_env is None:
            os.environ.pop(_ENV_KEY, None)
        else:
            os.environ[_ENV_KEY] = prev_env

        # Release the lock.
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(fd)


@contextmanager
def resolved_port_lock(
    port_override: str | None,
    caller: str,
    patterns: Sequence[str] | None = None,
) -> Generator[str, None, None]:
    """Resolve the port, acquire an exclusive lock, and yield the port string."""
    port = resolve_port(port_override, patterns)
    with port_lock(port, caller):
        yield port
