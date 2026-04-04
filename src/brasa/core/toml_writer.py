"""TOML writer — update the [firmware] section in brasa.toml."""

import re
from pathlib import Path

_SECTION_RE = re.compile(
    r"(?:^|\n)(\[firmware\]\n(?:[^\[]*?)?)(?=\n\[|\Z)",
    re.DOTALL,
)


def _render_firmware_section(board: str, variant: str, version: str, date: str) -> str:
    """Render a [firmware] TOML section."""
    lines = [
        "[firmware]",
        f'board = "{board}"',
        f'variant = "{variant}"',
        f'version = "{version}"',
        f'date = "{date}"',
    ]
    return "\n".join(lines) + "\n"


def pin_firmware(
    board: str,
    variant: str,
    version: str,
    date: str,
    *,
    config_path: Path | None = None,
) -> Path:
    """Write or update the [firmware] section in brasa.toml. Return the path."""
    path = config_path or Path.cwd() / "brasa.toml"
    section = _render_firmware_section(board, variant, version, date)

    if path.exists():
        content = path.read_text()
        if _SECTION_RE.search(content):
            content = _SECTION_RE.sub("\n" + section, content, count=1)
            # strip leading newline if at start of file
            content = content.lstrip("\n")
        else:
            if content and not content.endswith("\n"):
                content += "\n"
            content += "\n" + section
        path.write_text(content)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(section)

    return path
