"""Terminal output helpers — colored, tagged printing to stderr/stdout."""

import os
import sys

# ANSI escape codes
_RESET = "\033[0m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_GREEN = "\033[32m"
_CYAN = "\033[36m"
_DIM = "\033[2m"

CYAN = _CYAN
RED = _RED
YELLOW = _YELLOW
GREEN = _GREEN


def _no_color() -> bool:
    """Return True when ANSI codes should be suppressed (per https://no-color.org)."""
    return "NO_COLOR" in os.environ


def _wrap(text: str, code: str) -> str:
    if _no_color():
        return text
    return f"{code}{text}{_RESET}"


# ── Color helpers ────────────────────────────────────────────────────────────


def red(text: str) -> str:
    """Wrap *text* in red ANSI escape codes."""
    return _wrap(text, _RED)


def yellow(text: str) -> str:
    """Wrap *text* in yellow ANSI escape codes."""
    return _wrap(text, _YELLOW)


def green(text: str) -> str:
    """Wrap *text* in green ANSI escape codes."""
    return _wrap(text, _GREEN)


def cyan(text: str) -> str:
    """Wrap *text* in cyan ANSI escape codes."""
    return _wrap(text, _CYAN)


def dim(text: str) -> str:
    """Wrap *text* in dim ANSI escape codes."""
    return _wrap(text, _DIM)


# ── Tagged output ────────────────────────────────────────────────────────────


def status(tag: str, msg: str, color: str = CYAN) -> None:
    """Print ``[tag] msg`` to stderr with ANSI *color* on the tag."""
    colored_tag = _wrap(f"[{tag}]", color)
    print(f"{colored_tag} {msg}", file=sys.stderr)


def error(msg: str) -> None:
    """Print a red ``[error] msg`` to stderr."""
    status("error", msg, color=RED)


def warn(msg: str) -> None:
    """Print a yellow ``[warning] msg`` to stderr."""
    status("warning", msg, color=YELLOW)


def success(msg: str) -> None:
    """Print a green ``[ok] msg`` to stderr."""
    status("ok", msg, color=GREEN)


# ── Stdout helper ────────────────────────────────────────────────────────────


def print_stdout(msg: str) -> None:
    """Print *msg* to stdout with ``flush=True`` (for real-time serial output)."""
    print(msg, file=sys.stdout, flush=True)
