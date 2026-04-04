"""Tests for brasa.core.toml_writer — TOML [firmware] section writing."""

from pathlib import Path

from brasa.core.toml_writer import pin_firmware


def test_pin_creates_file_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "brasa.toml"
    result = pin_firmware(
        "ESP32_GENERIC", "SPIRAM", "1.27.0", "20251209", config_path=path
    )
    assert result == path
    content = path.read_text()
    assert "[firmware]" in content
    assert 'board = "ESP32_GENERIC"' in content
    assert 'variant = "SPIRAM"' in content
    assert 'version = "1.27.0"' in content
    assert 'date = "20251209"' in content


def test_pin_updates_existing_firmware_section(tmp_path: Path) -> None:
    path = tmp_path / "brasa.toml"
    path.write_text(
        '[firmware]\nboard = "OLD"\nvariant = "OLD"\nversion = "0.0.1"\ndate = "20200101"\n'
    )
    pin_firmware("ESP32_GENERIC", "", "1.27.0", "20251209", config_path=path)
    content = path.read_text()
    assert 'board = "ESP32_GENERIC"' in content
    assert "OLD" not in content


def test_pin_appends_to_file_without_firmware(tmp_path: Path) -> None:
    path = tmp_path / "brasa.toml"
    path.write_text('[deploy]\nsrc = "src"\n')
    pin_firmware("ESP32_GENERIC", "", "1.27.0", "20251209", config_path=path)
    content = path.read_text()
    assert "[deploy]" in content
    assert "[firmware]" in content
    assert 'src = "src"' in content


def test_pin_preserves_other_sections(tmp_path: Path) -> None:
    path = tmp_path / "brasa.toml"
    original = '[deploy]\nsrc = "src"\n\n[serial]\nbaud_rate = 115200\n'
    path.write_text(original)
    pin_firmware("ESP32_GENERIC", "", "1.27.0", "20251209", config_path=path)
    content = path.read_text()
    assert "[deploy]" in content
    assert "[serial]" in content
    assert "baud_rate = 115200" in content
