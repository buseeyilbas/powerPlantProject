# conftest.py
"""
Pytest configuration for unit tests:
- Adds the project 'scripts' folder to sys.path so we can import extract_zip.py
- Provides reusable fixtures to create sample ZIPs in temp folders.
"""

import os
import sys
import pytest
import zipfile
import io
from pathlib import Path

SCRIPTS_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\scripts"

# Ensure we can import modules from the scripts directory
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)



@pytest.fixture
def temp_download_dir(tmp_path):
    """Returns a temporary folder path to be used as destination_folder in tests."""
    return tmp_path



@pytest.fixture
def sample_url():
    """A realistic MaStR export URL that ends with a filename."""
    return "https://download.marktstammdatenregister.de/Gesamtdatenexport_20990101_25.1.zip"


@pytest.fixture
def make_zip(tmp_path: Path):
    """
    Factory fixture to create a .zip file with given files.

    Usage:
        zip_path = make_zip("dataset1.zip", {"a.txt": b"AAA", "b/c.txt": b"CCC"})
    """
    def _make(zip_name: str, files: dict) -> Path:
        zip_path = tmp_path / zip_name
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for arcname, content in files.items():
                if isinstance(content, str):
                    content = content.encode("utf-8")
                zf.writestr(arcname, content)
        return zip_path
    return _make
