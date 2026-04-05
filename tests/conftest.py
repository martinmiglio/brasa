"""Shared test fixtures for brasa."""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture()
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a minimal project layout and chdir into it.

    Layout::

        tmp_path/
        ├── src/
        │   ├── app.py
        │   └── utils.py
        ├── .env
        ├── boot.py
        └── main.py
    """
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("# app")
    (src / "utils.py").write_text("# utils")
    (tmp_path / ".env").write_text("SECRET=123")
    (tmp_path / "boot.py").write_text("# boot")
    (tmp_path / "main.py").write_text("# main")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@contextmanager
def fake_port_lock(
    port_override: str | None, caller: str, patterns: object = None
) -> Generator[str, None, None]:
    """Stand-in for resolved_port_lock that skips real locking."""
    yield port_override or "/dev/cu.test"
