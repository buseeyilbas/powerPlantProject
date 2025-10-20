# test_3_validate_xml.py
"""
Unit tests for step3_validate_xml module.
Tests XML validation and selective copying behavior.
"""

import os
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
import shutil

# ✅ standardized alias import
import step3_validate_xml as validate_xml


def test_is_valid_xml_true_and_false(tmp_path, capsys):
    """Checks that valid XML returns True and invalid XML returns False."""
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
    """Only valid XMLs should be copied to output_dir."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    valid_file = input_dir / "a.xml"
    valid_file.write_text("<root><child/></root>", encoding="utf-8")

    invalid_file = input_dir / "b.xml"
    invalid_file.write_text("<root><child></root>", encoding="utf-8")

    non_xml = input_dir / "ignore.txt"
    non_xml.write_text("Just text", encoding="utf-8")

    validate_xml.validate_and_copy_xmls(str(input_dir), str(output_dir))

    copied_files = [p.name for p in output_dir.iterdir()]
    assert copied_files == ["a.xml"]

    out = capsys.readouterr().out
    assert "📄 Scanning: a.xml" in out
    assert "📄 Scanning: b.xml" in out
    assert "✅ Valid: 1" in out
    assert "❌ Invalid: 1" in out
    assert "📁 Valid XMLs copied to:" in out


def test_validate_and_copy_xmls_empty_folder(tmp_path, capsys):
    """Empty folder → no files copied, printed summary must show zeros."""
    input_dir = tmp_path / "empty"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    validate_xml.validate_and_copy_xmls(str(input_dir), str(output_dir))

    assert not any(output_dir.iterdir())
    out = capsys.readouterr().out
    assert "XML files scanned: 0" in out
    assert "Valid: 0" in out


# --- Run standalone ---
if __name__ == "__main__":
    pytest.main(["-v", __file__])
