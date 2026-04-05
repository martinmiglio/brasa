"""TOML writer — update config sections in brasa.toml or pyproject.toml."""

import re
from pathlib import Path

from brasa.core.config import resolve_config_write_path


def _section_header(path: Path, section: str) -> str:
    """Return the TOML section header, adding the ``tool.brasa.`` prefix for pyproject.toml."""
    if path.name == "pyproject.toml":
        return f"tool.brasa.{section}"
    return section


def _section_re(header: str) -> re.Pattern[str]:
    """Build a regex that matches a TOML section by its header."""
    escaped = re.escape(header)
    return re.compile(
        rf"(?:^|\n)(\[{escaped}\]\n(?:[^\[]*?)?)(?=\n\[|\Z)",
        re.DOTALL,
    )


def _render_section(header: str, fields: dict[str, str]) -> str:
    """Render a TOML section with the given header and key-value pairs."""
    lines = [f"[{header}]"]
    for key, value in fields.items():
        lines.append(f'{key} = "{value}"')
    return "\n".join(lines) + "\n"


def pin_firmware(
    board: str,
    variant: str,
    version: str,
    date: str,
    *,
    config_path: Path | None = None,
) -> Path:
    """Write or update the [firmware] section in the config file. Return the path."""
    path = config_path or resolve_config_write_path()
    header = _section_header(path, "firmware")
    section = _render_section(
        header,
        {
            "board": board,
            "variant": variant,
            "version": version,
            "date": date,
        },
    )
    pattern = _section_re(header)

    if path.exists():
        content = path.read_text()
        if pattern.search(content):
            content = pattern.sub("\n" + section, content, count=1)
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
