"""
Unit tests for step4_xml_to_json module.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step4_xml_to_json as xml_to_json


def test_xml_file_to_json_valid_file_creates_expected_json(tmp_path, capsys):
    """Valid XML should be converted into a JSON list of dictionaries."""
    xml_file = tmp_path / "valid.xml"
    xml_file.write_text(
        "<root>"
        "<item><name>Test1</name><value>123</value></item>"
        "<item><name>Test2</name><value>456</value></item>"
        "</root>",
        encoding="utf-8",
    )
    json_output = tmp_path / "valid.json"

    xml_to_json.xml_file_to_json(str(xml_file), str(json_output))

    assert json_output.exists()
    data = json.loads(json_output.read_text(encoding="utf-8"))
    assert data == [
        {"name": "Test1", "value": "123"},
        {"name": "Test2", "value": "456"},
    ]

    out = capsys.readouterr().out
    assert "✔ Converted valid.xml to valid.json" in out


def test_xml_file_to_json_invalid_file_does_not_create_output(tmp_path, capsys):
    """Invalid XML should not create a JSON file and should print a warning."""
    invalid_xml = tmp_path / "invalid.xml"
    invalid_xml.write_text("<root><broken></root>", encoding="utf-8")
    json_output = tmp_path / "invalid.json"

    xml_to_json.xml_file_to_json(str(invalid_xml), str(json_output))

    assert not json_output.exists()

    out = capsys.readouterr().out
    assert "⚠️ Failed to convert" in out
    assert "invalid.xml" in out


def test_xml_file_to_json_handles_empty_root(tmp_path):
    """An XML file with an empty root should produce an empty JSON list."""
    xml_file = tmp_path / "empty.xml"
    xml_file.write_text("<root></root>", encoding="utf-8")
    json_output = tmp_path / "empty.json"

    xml_to_json.xml_file_to_json(str(xml_file), str(json_output))

    assert json_output.exists()
    data = json.loads(json_output.read_text(encoding="utf-8"))
    assert data == []


def test_batch_convert_xml_to_json_converts_multiple_files_and_skips_non_xml(tmp_path):
    """Batch conversion should convert multiple XML files and ignore non-XML files."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    (input_dir / "file1.xml").write_text("<root><row><a>1</a></row></root>", encoding="utf-8")
    (input_dir / "file2.xml").write_text("<root><row><b>2</b></row></root>", encoding="utf-8")
    (input_dir / "skip.txt").write_text("Not XML", encoding="utf-8")

    xml_to_json.batch_convert_xml_to_json(str(input_dir), str(output_dir))

    files = sorted(p.name for p in output_dir.iterdir())
    assert files == ["file1.json", "file2.json"]

    data1 = json.loads((output_dir / "file1.json").read_text(encoding="utf-8"))
    data2 = json.loads((output_dir / "file2.json").read_text(encoding="utf-8"))

    assert data1 == [{"a": "1"}]
    assert data2 == [{"b": "2"}]


def test_batch_convert_xml_to_json_creates_output_folder(tmp_path):
    """Output folder should be created automatically when missing."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    (input_dir / "file1.xml").write_text("<root><row><a>1</a></row></root>", encoding="utf-8")

    assert not output_dir.exists()

    xml_to_json.batch_convert_xml_to_json(str(input_dir), str(output_dir))

    assert output_dir.exists()
    assert (output_dir / "file1.json").exists()


def test_batch_convert_xml_to_json_scans_nested_directories(tmp_path):
    """The function should convert XML files from nested folders because it uses os.walk."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    nested = input_dir / "nested" / "deeper"
    nested.mkdir(parents=True)

    (nested / "nested_file.xml").write_text("<root><row><a>42</a></row></root>", encoding="utf-8")

    xml_to_json.batch_convert_xml_to_json(str(input_dir), str(output_dir))

    assert (output_dir / "nested_file.json").exists()
    data = json.loads((output_dir / "nested_file.json").read_text(encoding="utf-8"))
    assert data == [{"a": "42"}]


def test_batch_convert_xml_to_json_skips_invalid_xml_but_continues(tmp_path):
    """Invalid XML in batch mode should not stop other valid files from converting."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    (input_dir / "good.xml").write_text("<root><row><a>1</a></row></root>", encoding="utf-8")
    (input_dir / "bad.xml").write_text("<root><row></root>", encoding="utf-8")

    xml_to_json.batch_convert_xml_to_json(str(input_dir), str(output_dir))

    assert (output_dir / "good.json").exists()
    assert not (output_dir / "bad.json").exists()


def test_batch_convert_xml_to_json_ignores_uppercase_xml_extension(tmp_path):
    """Current implementation is case-sensitive and should ignore .XML files."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    (input_dir / "UPPER.XML").write_text("<root><row><a>1</a></row></root>", encoding="utf-8")

    xml_to_json.batch_convert_xml_to_json(str(input_dir), str(output_dir))

    assert output_dir.exists()
    assert list(output_dir.iterdir()) == []


def test_batch_convert_xml_to_json_same_filename_collision(tmp_path):
    """Files with the same name in different folders currently collide in output."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"

    dir_a = input_dir / "a"
    dir_b = input_dir / "b"
    dir_a.mkdir(parents=True)
    dir_b.mkdir(parents=True)

    (dir_a / "same.xml").write_text("<root><row><value>A</value></row></root>", encoding="utf-8")
    (dir_b / "same.xml").write_text("<root><row><value>B</value></row></root>", encoding="utf-8")

    xml_to_json.batch_convert_xml_to_json(str(input_dir), str(output_dir))

    output_file = output_dir / "same.json"
    assert output_file.exists()

    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert data in [[{"value": "A"}], [{"value": "B"}]]