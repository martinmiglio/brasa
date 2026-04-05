"""Tests for brasa.core.lock — port locking with fcntl."""

import fcntl
import json
import os

import pytest

from brasa.core.lock import _ENV_KEY, _lock_path, port_lock, resolved_port_lock


@pytest.fixture(autouse=True)
def _use_tmp_path_for_locks(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    """Redirect lock files into the test's tmp directory."""
    monkeypatch.setattr("brasa.core.lock._LOCK_DIR", str(tmp_path))


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure BRASA_PORT_LOCKED is unset before each test."""
    monkeypatch.delenv(_ENV_KEY, raising=False)


PORT = "/dev/cu.usbmodem1234"
CALLER = "deploy"


class TestPortLockHappyPath:
    """Lock acquired, metadata written, env set/restored."""

    def test_lock_acquired(self, tmp_path: object) -> None:
        with port_lock(PORT, CALLER):
            lock_file = _lock_path(PORT)
            assert os.path.exists(lock_file)

    def test_writes_correct_metadata(self, tmp_path: object) -> None:
        with port_lock(PORT, CALLER):
            lock_file = _lock_path(PORT)
            with open(lock_file) as f:
                data = json.load(f)
            assert data["pid"] == os.getpid()
            assert data["caller"] == CALLER

    def test_env_var_set_inside_context(self) -> None:
        with port_lock(PORT, CALLER):
            assert os.environ.get(_ENV_KEY) == PORT

    def test_env_var_restored_after_context(self) -> None:
        with port_lock(PORT, CALLER):
            pass
        assert os.environ.get(_ENV_KEY) is None


class TestReentrant:
    """When BRASA_PORT_LOCKED is already set to the port, skip locking."""

    def test_reentrant_skips_lock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(_ENV_KEY, PORT)
        # Should not raise or attempt to acquire — just yield.
        with port_lock(PORT, CALLER):
            # Env var should still be present (unchanged).
            assert os.environ[_ENV_KEY] == PORT

    def test_reentrant_no_lock_file_created(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(_ENV_KEY, PORT)
        with port_lock(PORT, CALLER):
            assert not os.path.exists(_lock_path(PORT))


class TestKeyboardInterrupt:
    """KeyboardInterrupt inside the lock raises SystemExit(130)."""

    def test_keyboard_interrupt_exits_130(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original_flock = fcntl.flock

        call_count = 0

        def flock_then_interrupt(fd: int, op: int) -> None:
            nonlocal call_count
            call_count += 1
            original_flock(fd, op)
            # Raise after the lock is acquired (first LOCK_EX call).
            if call_count == 1:
                raise KeyboardInterrupt

        monkeypatch.setattr("fcntl.flock", flock_then_interrupt)

        with pytest.raises(SystemExit, match="130"):
            with port_lock(PORT, CALLER):
                pass  # pragma: no cover


class TestContention:
    """Mock fcntl.flock to simulate contention."""

    def test_contention_blocks_then_acquires(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original_flock = fcntl.flock
        calls: list[int] = []
        nb_attempts = 0

        def flock_contention(fd: int, op: int) -> None:
            nonlocal nb_attempts
            calls.append(op)
            if op == (fcntl.LOCK_EX | fcntl.LOCK_NB):
                nb_attempts += 1
                if nb_attempts <= 2:
                    raise BlockingIOError("locked by another process")
            # Third NB attempt (or unlock) succeeds.
            original_flock(fd, op)

        monkeypatch.setattr("fcntl.flock", flock_contention)

        with port_lock(PORT, CALLER):
            pass

        # First two NB attempts fail, third succeeds, then unlock.
        assert calls[0] == fcntl.LOCK_EX | fcntl.LOCK_NB
        assert nb_attempts >= 2


class TestResolvedPortLock:
    """Combined resolve + lock context manager."""

    def test_yields_resolved_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "brasa.core.lock.resolve_port", lambda override, patterns=None: PORT
        )
        with resolved_port_lock(None, CALLER) as port:
            assert port == PORT
            assert os.environ.get(_ENV_KEY) == PORT

    def test_passes_override_to_resolve(self, monkeypatch: pytest.MonkeyPatch) -> None:
        received: list[tuple[str | None, object]] = []

        def fake_resolve(override: str | None, patterns: object = None) -> str:
            received.append((override, patterns))
            return "/dev/cu.override"

        monkeypatch.setattr("brasa.core.lock.resolve_port", fake_resolve)
        with resolved_port_lock("/dev/cu.override", CALLER) as port:
            assert port == "/dev/cu.override"
        assert received[0] == ("/dev/cu.override", None)

    def test_passes_patterns_to_resolve(self, monkeypatch: pytest.MonkeyPatch) -> None:
        received_patterns: list[object] = []

        def fake_resolve(override: str | None, patterns: object = None) -> str:
            received_patterns.append(patterns)
            return PORT

        monkeypatch.setattr("brasa.core.lock.resolve_port", fake_resolve)
        with resolved_port_lock(None, CALLER, patterns=["cu.custom*"]) as port:
            assert port == PORT
        assert received_patterns[0] == ["cu.custom*"]
