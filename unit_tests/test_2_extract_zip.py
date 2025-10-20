# test_extract_zip.py
"""
Unit tests for extract_zip.extract_all_zips using pytest.

We exercise these behaviors:
1) If input_dir does not exist -> prints message and returns (no output dir created).
2) If there are no .zip files -> prints message and returns.
3) Creates output_dir when missing and extracts contents.
4) Extracts multiple ZIPs into separate subfolders (named after ZIP basename).
5) Ignores non-zip files in input_dir.
6) Bad/corrupted ZIP -> zipfile.BadZipFile propagates (no silent swallow).
7) Progress messages include "Extracting ..." and "Done extracting".
"""

import os
import zipfile
from pathlib import Path

import step2_extract_zip as extract_zip  # imported via conftest.py sys.path edit


# Test case for input directory does not exist
def test_input_folder_missing(capsys, tmp_path):
    input_dir = tmp_path / "does_not_exist"
    output_dir = tmp_path / "out"

    # Precondition
    assert not input_dir.exists()
    assert not output_dir.exists()

    extract_zip.extract_all_zips(str(input_dir), str(output_dir))

    # Output dir must NOT be created when input is missing
    assert not output_dir.exists()

    out = capsys.readouterr().out
    assert f"Input folder does not exist: {input_dir}" in out


# Test case for no ZIP files (empty) in input directory
def test_no_zip_files(capsys, tmp_path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "note.txt").write_text("hello")  # non-zip file

    extract_zip.extract_all_zips(str(input_dir), str(output_dir))

    # Output dir should be created but no extraction subfolders
    assert output_dir.exists()
    # It should be empty
    assert list(output_dir.iterdir()) == []

    out = capsys.readouterr().out
    assert "No ZIP files found in input directory." in out


# Test case for extracting a single ZIP file with nested structure
def test_creates_output_dir_and_extracts_single_zip(make_zip, capsys, tmp_path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir(parents=True, exist_ok=True)

    # Create a ZIP with nested structure
    zip_path = make_zip("archive_001.zip", {
        "a.txt": b"AAA",
        "nested/b.txt": b"BBB",
    })
    # Move the generated ZIP into our input_dir if not already there
    Path(zip_path).replace(input_dir / Path(zip_path).name)

    # Ensure output_dir does not exist yet
    assert not output_dir.exists()

    extract_zip.extract_all_zips(str(input_dir), str(output_dir))

    # Output dir created
    assert output_dir.exists()

    # ZIP should be extracted into folder named after ZIP (without extension)
    extract_folder = output_dir / "archive_001"
    assert extract_folder.exists() and extract_folder.is_dir()

    # Files are extracted with original structure and content
    assert (extract_folder / "a.txt").read_bytes() == b"AAA"
    assert (extract_folder / "nested" / "b.txt").read_bytes() == b"BBB"

    out = capsys.readouterr().out
    assert "Extracting archive_001.zip to" in out
    assert "✔ Done extracting archive_001.zip." in out


# Test case for extracting multiple ZIP files into separate folders
def test_extracts_multiple_zips_into_separate_folders(make_zip, tmp_path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir(parents=True, exist_ok=True)

    z1 = Path(make_zip("first.zip", {"x.txt": b"X"}))
    z2 = Path(make_zip("second.zip", {"y.txt": b"Y"}))
    z1.replace(input_dir / z1.name)
    z2.replace(input_dir / z2.name)

    extract_zip.extract_all_zips(str(input_dir), str(output_dir))

    # Two separate extraction folders
    f1 = output_dir / "first"
    f2 = output_dir / "second"
    assert f1.exists() and f2.exists()
    assert (f1 / "x.txt").read_bytes() == b"X"
    assert (f2 / "y.txt").read_bytes() == b"Y"


# Test case for ignoring non-zip files in input directory
def test_ignores_non_zip_files(make_zip, tmp_path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir(parents=True, exist_ok=True)

    # One zip + other extensions
    z = Path(make_zip("real.zip", {"d.txt": b"D"}))
    z.replace(input_dir / z.name)
    (input_dir / "image.png").write_bytes(b"\x89PNG\r\n")
    (input_dir / "doc.pdf").write_bytes(b"%PDF-1.7")
    (input_dir / "notes.zip.bak").write_bytes(b"not a real zip")

    extract_zip.extract_all_zips(str(input_dir), str(output_dir))

    # Only real.zip extracted
    folder = output_dir / "real"
    assert folder.exists()
    assert (folder / "d.txt").read_bytes() == b"D"
    # No other random folders
    others = [p for p in output_dir.iterdir() if p.name != "real"]
    assert others == []


# Test case for handling bad/corrupted ZIP files
def test_bad_zip_raises_badzipfile(tmp_path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir(parents=True, exist_ok=True)

    # Create an invalid .zip file (just some bytes)
    bad_zip = input_dir / "corrupted.zip"
    bad_zip.write_bytes(b"NOT_A_ZIP")

    # The function does not catch exceptions -> expect BadZipFile
    try:
        extract_zip.extract_all_zips(str(input_dir), str(output_dir))
        assert False, "Expected zipfile.BadZipFile to be raised"
    except zipfile.BadZipFile:
        pass
