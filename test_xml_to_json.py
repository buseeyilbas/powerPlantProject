# test_xml_to_json.py

import json
from pathlib import Path
import pytest
import xml_to_json as mod


def test_xml_file_to_json_valid_and_invalid(tmp_path, capsys):
    # Arrange: valid XML file
    valid_xml = tmp_path / "valid.xml"
    valid_xml.write_text(
        "<root><item><name>Test1</name><value>123</value></item><item><name>Test2</name><value>456</value></item></root>",
        encoding="utf-8"
    )
    json_output = tmp_path / "valid.json"

    # Act
    mod.xml_file_to_json(str(valid_xml), str(json_output))

    # Assert valid conversion
    assert json_output.exists()
    data = json.loads(json_output.read_text(encoding="utf-8"))
    assert data == [
        {"name": "Test1", "value": "123"},
        {"name": "Test2", "value": "456"}
    ]
    out = capsys.readouterr().out
    assert "✔ Converted valid.xml" in out

    # Arrange: invalid XML
    invalid_xml = tmp_path / "invalid.xml"
    invalid_xml.write_text("<root><broken></root>", encoding="utf-8")
    json_output_invalid = tmp_path / "invalid.json"

    # Act
    mod.xml_file_to_json(str(invalid_xml), str(json_output_invalid))

    # Assert: no file created for invalid XML
    assert not json_output_invalid.exists()
    err_out = capsys.readouterr().out
    assert "⚠️ Failed to convert" in err_out
    assert "invalid.xml" in err_out


def test_batch_convert_xml_to_json(tmp_path):
    # Arrange: input folder with 2 XML files
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    xml1 = input_dir / "file1.xml"
    xml1.write_text("<root><row><a>1</a></row></root>", encoding="utf-8")

    xml2 = input_dir / "file2.xml"
    xml2.write_text("<root><row><b>2</b></row></root>", encoding="utf-8")

    # Also add a non-XML file to ensure it is skipped
    (input_dir / "skip.txt").write_text("Not XML", encoding="utf-8")

    # Act
    mod.batch_convert_xml_to_json(str(input_dir), str(output_dir))

    # Assert: two JSON files created
    files = sorted([p.name for p in output_dir.iterdir()])
    assert files == ["file1.json", "file2.json"]

    # Validate JSON contents
    data1 = json.loads((output_dir / "file1.json").read_text(encoding="utf-8"))
    assert data1 == [{"a": "1"}]
    data2 = json.loads((output_dir / "file2.json").read_text(encoding="utf-8"))
    assert data2 == [{"b": "2"}]
