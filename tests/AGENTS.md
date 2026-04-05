# AGENTS.md — brasa/tests

## Philosophy

- **Test behavior, not implementation.** Assert outcomes ("files were deployed", "output contains board name") — not mock call counts, argument positions, or internal function invocations.
- **Prefer real objects over mocks.** Use `tmp_path` with real files, `freezegun` for time control, real TOML parsing. Only mock at system boundaries (subprocess calls to mpremote/esptool, serial ports, network I/O).
- **Use synchronization, not sleeps.** Threading tests must use `threading.Event`, `Condition`, or `queue.Queue` — never `time.sleep`.

## Conventions

### File naming

`test_<module>.py` corresponding to `brasa.core.<module>` or `brasa.commands.<module>`. Group related tests in classes with descriptive names (e.g., `TestResolveBoard`, `TestCacheFreshness`).

### Fixtures

- **Shared fixtures** (used by 2+ files) live in `conftest.py`.
- **File-local fixtures** stay in the test file.
- Prefer explicit `@pytest.fixture` over helper dicts of patches (e.g., `_make_patches()`). Each test should declare its dependencies clearly.

### Mocking rules

1. **Subprocess boundary:** Use `pytest-subprocess` (`fp` fixture) for mpremote/esptool — it's already a dependency and gives realistic subprocess simulation.
2. **Time:** Use `freezegun` (`@freeze_time` or `freeze_time` context manager) for cache freshness, timeouts, and any time-dependent logic.
3. **File system:** Use `tmp_path` with real files. Don't mock `Path`, `open`, or `os` unless absolutely necessary.
4. **Network:** Mock `urllib.request.urlopen` or use `pytest-subprocess` for download commands.
5. **Never mock the thing you're testing.** If testing cache behavior, don't mock `_is_fresh` or `_load_index` — use real temp files and control time instead.

### Assertions

- Assert on outcomes, not call sequences. "The file exists with correct content" beats "fs_cp was called with these exact args".
- Use `in` checks for output text, not exact string matches. Wording changes shouldn't break tests.
- Use `@pytest.mark.parametrize` for variant testing (board types, config sources, error cases) instead of copy-pasting tests.

### Markers

- `@pytest.mark.hardware` — requires a physical device. CI runs with `-m "not hardware"`.
- Default timeout is 10s per test (configured in pyproject.toml).

### Threading tests

- Signal completion with `threading.Event.set()` and wait with `event.wait(timeout=2)`.
- This is fast when it works and provides a safe timeout for CI — no flaky sleeps.

## Shared fixtures (conftest.py)

| Fixture | Purpose |
|---------|---------|
| `project_dir` | Creates `src/`, `boot.py`, `main.py`, `.env` in `tmp_path` and chdirs into it |

## Running tests

```bash
uv run pytest                          # all tests (except hardware)
uv run pytest -m hardware              # only hardware tests
uv run pytest --cov=brasa              # with coverage
uv run pytest tests/test_deploy.py -v  # single file, verbose
```
