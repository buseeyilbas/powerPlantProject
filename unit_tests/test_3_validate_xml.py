"""
Unit tests for step3_validate_xml module.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step3_validate_xml as validate_xml


def test_is_valid_xml_true_and_false(tmp_path, capsys):
    """Valid XML should return True, invalid XML should return False."""
    valid_file = tmp_path / "valid.xml"
    valid_file.write_text("<root><child>data</child></root>", encoding="utf-8")

    invalid_file = tmp_path / "invalid.xml"
    invalid_file.write_text("<root><child></root>", encoding="utf-8")

    assert validate_xml.is_valid_xml(str(valid_file)) is True
    out_valid = capsys.readouterr().out
    assert f"📄 Scanning: {valid_file.name}" in out_valid

    assert validate_xml.is_valid_xml(str(invalid_file)) is False
    out_invalid = capsys.readouterr().out
    assert "❌ Invalid XML" in out_invalid
    assert invalid_file.name in out_invalid


def test_validate_and_copy_xmls_mixed_files(tmp_path, capsys):
    """Only valid XML files should be copied."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    (input_dir / "a.xml").write_text("<root><child/></root>", encoding="utf-8")
    (input_dir / "b.xml").write_text("<root><child></root>", encoding="utf-8")
    (input_dir / "ignore.txt").write_text("Just text", encoding="utf-8")

    validate_xml.validate_and_copy_xmls(str(input_dir), str(output_dir))

    copied_files = sorted(p.name for p in output_dir.iterdir())
    assert copied_files == ["a.xml"]

    out = capsys.readouterr().out
    assert "📄 Scanning: a.xml" in out
    assert "📄 Scanning: b.xml" in out
    assert "XML files scanned: 2" in out
    assert "✅ Valid: 1" in out
    assert "❌ Invalid: 1" in out
    assert "📁 Valid XMLs copied to:" in out


def test_validate_and_copy_xmls_empty_folder(tmp_path, capsys):
    """Empty input should produce zero counts and no copied files."""
    input_dir = tmp_path / "empty"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    validate_xml.validate_and_copy_xmls(str(input_dir), str(output_dir))

    assert output_dir.exists()
    assert list(output_dir.iterdir()) == []

    out = capsys.readouterr().out
    assert "XML files scanned: 0" in out
    assert "Valid: 0" in out
    assert "Invalid: 0" in out


def test_validate_and_copy_xmls_creates_output_folder(tmp_path):
    """Output folder should be created automatically if it does not exist."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "new_output"
    input_dir.mkdir()

    (input_dir / "a.xml").write_text("<root/>", encoding="utf-8")

    assert not output_dir.exists()

    validate_xml.validate_and_copy_xmls(str(input_dir), str(output_dir))

    assert output_dir.exists()
    assert (output_dir / "a.xml").exists()


def test_validate_and_copy_xmls_scans_nested_directories(tmp_path):
    """Function should find XML files in subdirectories because it uses os.walk."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    nested_dir = input_dir / "nested" / "deeper"

    nested_dir.mkdir(parents=True)

    (nested_dir / "nested_valid.xml").write_text("<root><x/></root>", encoding="utf-8")
    (nested_dir / "nested_invalid.xml").write_text("<root><x></root>", encoding="utf-8")

    validate_xml.validate_and_copy_xmls(str(input_dir), str(output_dir))

    assert (output_dir / "nested_valid.xml").exists()
    assert not (output_dir / "nested_invalid.xml").exists()


def test_validate_and_copy_xmls_ignores_uppercase_xml_extension(tmp_path):
    """Current implementation is case-sensitive and ignores .XML files."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    (input_dir / "upper.XML").write_text("<root/>", encoding="utf-8")

    validate_xml.validate_and_copy_xmls(str(input_dir), str(output_dir))

    assert output_dir.exists()
    assert list(output_dir.iterdir()) == []


def test_validate_and_copy_xmls_same_filename_collision_overwrites(tmp_path):
    """Files with the same name in different subfolders currently collide in the output folder."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"

    folder_a = input_dir / "a"
    folder_b = input_dir / "b"
    folder_a.mkdir(parents=True)
    folder_b.mkdir(parents=True)

    (folder_a / "same.xml").write_text("<root><value>A</value></root>", encoding="utf-8")
    (folder_b / "same.xml").write_text("<root><value>B</value></root>", encoding="utf-8")

    validate_xml.validate_and_copy_xmls(str(input_dir), str(output_dir))

    copied = output_dir / "same.xml"
    assert copied.exists()

    text = copied.read_text(encoding="utf-8")
    assert text in {
        "<root><value>A</value></root>",
        "<root><value>B</value></root>",
    }