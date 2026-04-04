"""Serial port auto-detection with USB tree fallback for driver hints."""

import glob
import json
import subprocess
from collections.abc import Sequence
from typing import Any

from brasa.core import output

DEFAULT_PATTERNS: list[str] = [
    "/dev/cu.usbserial*",
    "/dev/cu.wchusbserial*",
    "/dev/cu.SLAB_USBtoUART*",
]

_KNOWN_VENDOR_IDS: dict[str, str] = {
    "0x1a86": "CH340 (try: brew install ch34x-driver)",
    "0x10c4": "CP2102 (try: brew install silabs-cp2102-driver)",
}


def detect_port(patterns: Sequence[str] | None = None) -> str:
    """Detect a serial port by globbing *patterns*.

    Returns the port path on success.  Calls :func:`_usb_tree_fallback` and
    raises ``SystemExit(1)`` when no port is found.
    """
    if patterns is None:
        patterns = DEFAULT_PATTERNS

    matches: list[str] = []
    for pattern in patterns:
        matches.extend(glob.glob(pattern))

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        output.warn(f"multiple serial ports found: {', '.join(matches)}")
        return matches[0]

    # No matches — run diagnostics then exit.
    output.error("no serial port found")
    _usb_tree_fallback()
    raise SystemExit(1)


def _usb_tree_fallback() -> None:
    """Inspect the macOS USB tree for devices and suggest driver fixes."""
    try:
        result = subprocess.run(
            ["system_profiler", "SPUSBDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        output.error("could not query USB devices — check connection and try again")
        return

    devices = _extract_usb_devices(data)
    if not devices:
        output.error("no USB devices detected — check your cable")
        return

    for device in devices:
        vendor_id = device.get("vendor_id", "")
        name = device.get("_name", "unknown device")
        hint = _KNOWN_VENDOR_IDS.get(vendor_id)
        if hint:
            output.warn(f"found USB device '{name}' but no serial port — {hint}")
            return

    # USB devices present but no known vendor ID matched.
    output.warn("USB device(s) detected but no matching serial driver found")


def _extract_usb_devices(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Recursively pull USB device entries from system_profiler JSON."""
    devices: list[dict[str, Any]] = []
    items = data.get("SPUSBDataType", [])
    if isinstance(items, list):
        _walk_items(items, devices)
    return devices


def _walk_items(items: list[Any], acc: list[dict[str, Any]]) -> None:
    for item in items:
        if not isinstance(item, dict):
            continue
        # A device entry has a vendor_id key; hubs may just nest children.
        if "vendor_id" in item:
            acc.append(item)
        children = item.get("_items")
        if isinstance(children, list):
            _walk_items(children, acc)
