"""
Unit tests for step2_extract_zip.extract_all_zips using pytest.
"""

import sys
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step2_extract_zip as extract_zip


def test_input_folder_missing(capsys, tmp_path):
    """Should print a message and return when input folder does not exist."""
    input_dir = tmp_path / "does_not_exist"
    output_dir = tmp_path / "out"

    assert not input_dir.exists()
    assert not output_dir.exists()

    extract_zip.extract_all_zips(str(input_dir), str(output_dir))

    assert not output_dir.exists()

    out = capsys.readouterr().out
    assert f"Input folder does not exist: {input_dir}" in out


def test_no_zip_files_creates_output_dir_and_returns(capsys, tmp_path):
    """Should create output directory, print a message, and extract nothing if no .zip files exist."""
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "note.txt").write_text("hello", encoding="utf-8")

    extract_zip.extract_all_zips(str(input_dir), str(output_dir))

    assert output_dir.exists()
    assert list(output_dir.iterdir()) == []

    out = capsys.readouterr().out
    assert "No ZIP files found in input directory." in out


def test_creates_output_dir_and_extracts_single_zip(make_zip, capsys, tmp_path):
    """Should create output directory and extract one ZIP into a same-name subfolder."""
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir(parents=True, exist_ok=True)

    zip_path = Path(make_zip("archive_001.zip", {
        "a.txt": b"AAA",
        "nested/b.txt": b"BBB",
    }))
    zip_path.replace(input_dir / zip_path.name)

    assert not output_dir.exists()

    extract_zip.extract_all_zips(str(input_dir), str(output_dir))

    extract_folder = output_dir / "archive_001"

    assert output_dir.exists()
    assert extract_folder.exists()
    assert extract_folder.is_dir()
    assert (extract_folder / "a.txt").read_bytes() == b"AAA"
    assert (extract_folder / "nested" / "b.txt").read_bytes() == b"BBB"

    out = capsys.readouterr().out
    assert "Extracting archive_001.zip to" in out
    assert "✔ Done extracting archive_001.zip." in out


def test_extracts_multiple_zips_into_separate_folders(make_zip, tmp_path):
    """Should extract multiple ZIP files into separate output subfolders."""
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir(parents=True, exist_ok=True)

    z1 = Path(make_zip("first.zip", {"x.txt": b"X"}))
    z2 = Path(make_zip("second.zip", {"y.txt": b"Y"}))
    z1.replace(input_dir / z1.name)
    z2.replace(input_dir / z2.name)

    extract_zip.extract_all_zips(str(input_dir), str(output_dir))

    f1 = output_dir / "first"
    f2 = output_dir / "second"

    assert f1.exists()
    assert f2.exists()
    assert (f1 / "x.txt").read_bytes() == b"X"
    assert (f2 / "y.txt").read_bytes() == b"Y"


def test_ignores_non_zip_files(make_zip, tmp_path):
    """Should ignore files that do not literally end with .zip."""
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir(parents=True, exist_ok=True)

    z = Path(make_zip("real.zip", {"d.txt": b"D"}))
    z.replace(input_dir / z.name)

    (input_dir / "image.png").write_bytes(b"\x89PNG\r\n")
    (input_dir / "doc.pdf").write_bytes(b"%PDF-1.7")
    (input_dir / "notes.zip.bak").write_bytes(b"not a real zip")

    extract_zip.extract_all_zips(str(input_dir), str(output_dir))

    folder = output_dir / "real"
    assert folder.exists()
    assert (folder / "d.txt").read_bytes() == b"D"

    others = [p for p in output_dir.iterdir() if p.name != "real"]
    assert others == []


def test_uppercase_zip_extension_is_ignored(tmp_path):
    """Current implementation is case-sensitive and should ignore .ZIP files."""
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir(parents=True, exist_ok=True)

    uppercase_zip = input_dir / "UPPER.ZIP"
    with zipfile.ZipFile(uppercase_zip, "w") as zf:
        zf.writestr("inside.txt", "hello")

    extract_zip.extract_all_zips(str(input_dir), str(output_dir))

    assert output_dir.exists()
    assert list(output_dir.iterdir()) == []


def test_bad_zip_raises_badzipfile(tmp_path):
    """Should propagate zipfile.BadZipFile for corrupted ZIP input."""
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir(parents=True, exist_ok=True)

    bad_zip = input_dir / "corrupted.zip"
    bad_zip.write_bytes(b"NOT_A_ZIP")

    with pytest.raises(zipfile.BadZipFile):
        extract_zip.extract_all_zips(str(input_dir), str(output_dir))


def test_extracts_into_existing_subfolder(make_zip, tmp_path):
    """Should extract into an already existing destination subfolder without failing."""
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    existing_extract_dir = output_dir / "archive"
    existing_extract_dir.mkdir(parents=True, exist_ok=True)
    (existing_extract_dir / "old.txt").write_text("old", encoding="utf-8")

    zip_path = Path(make_zip("archive.zip", {"new.txt": b"NEW"}))
    zip_path.replace(input_dir / zip_path.name)

    extract_zip.extract_all_zips(str(input_dir), str(output_dir))

    assert (existing_extract_dir / "old.txt").read_text(encoding="utf-8") == "old"
    assert (existing_extract_dir / "new.txt").read_bytes() == b"NEW"