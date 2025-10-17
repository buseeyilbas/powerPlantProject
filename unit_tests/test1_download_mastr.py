# test_download_mastr.py
"""
Unit tests for download_mastr.download_file using pytest.
We mock 'requests.get' to avoid real network calls and assert filesystem effects.
"""

import os
from pathlib import Path
from unittest.mock import patch

import requests  # only for HTTPError type

import step1_download_mastr  # imported thanks to conftest.py sys.path injection


class FakeResponse:
    """A lightweight fake of requests.Response that supports the context manager protocol."""
    def __init__(self, status_code=200, chunks=None):
        self.status_code = status_code
        self._chunks = chunks or []
        self.iter_content_called_with = None

    # Context manager interface
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False  # do not suppress exceptions

    # Minimal API we use in download_mastr.py
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code} error from fake response")

    def iter_content(self, chunk_size=8192):
        self.iter_content_called_with = chunk_size
        for c in self._chunks:
            yield c


# Factory function to create a fake requests.get that returns a FakeResponse.
# This allows us to control the response status and content chunks.
def _fake_get_factory(status_code=200, chunks=None):
    """Returns a function that mimics requests.get and yields a FakeResponse."""
    def _fake_get(url, stream=False, **kwargs):
        # We intentionally ignore 'stream' and kwargs here; assertions will be done in the patch object.
        return FakeResponse(status_code=status_code, chunks=chunks)
    return _fake_get

# Tests for download_mastr.download_file function
def test_download_success_creates_folder_and_writes_file(temp_download_dir, sample_url, capsys):
    """Should create destination folder when missing, stream bytes to disk, and return the path."""
    dest = temp_download_dir / "raw"  # simulate a nested folder
    assert not dest.exists()  # precondition: folder does not exist

    # Prepare fake streamed chunks (bytes)
    chunks = [b"AAA", b"BBB", b"CCC"]

    with patch("download_mastr.requests.get", side_effect=_fake_get_factory(200, chunks)) as mock_get:
        result_path = download_mastr.download_file(sample_url, str(dest))

    # Filesystem assertions
    assert dest.exists() and dest.is_dir()
    expected_filename = os.path.basename(sample_url)
    expected_path = dest / expected_filename
    assert Path(result_path) == expected_path
    assert expected_path.exists() and expected_path.is_file()
    assert expected_path.read_bytes() == b"".join(chunks)

    # requests.get was called with stream=True
    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs.get("stream") is True

    # Printed messages include both starting and completion lines
    out = capsys.readouterr().out
    assert "Downloading" in out and "completed" in out


# Test that ensures the download function does not recreate an existing folder
def test_download_uses_existing_folder_without_recreating(temp_download_dir, sample_url, monkeypatch):
    """If destination folder exists, os.makedirs must not be called."""
    dest = temp_download_dir / "already_there"
    dest.mkdir(parents=True, exist_ok=True)

    calls = {"makedirs": 0}

    def fake_makedirs(path, exist_ok=False):
        calls["makedirs"] += 1
        os.makedirs(path, exist_ok=exist_ok)  # should not be hit if folder already exists

    # Patch os.makedirs with a wrapper that counts calls
    monkeypatch.setattr("download_mastr.os.makedirs", fake_makedirs)

    # Stream one small chunk
    with patch("download_mastr.requests.get", side_effect=_fake_get_factory(200, [b"X"])):
        download_mastr.download_file(sample_url, str(dest))

    # Since the directory existed, makedirs should not have been called
    assert calls["makedirs"] == 0


# Test that ensures the download function passes the correct chunk size to iter_content
def test_download_stream_chunk_size_is_8192(sample_url, temp_download_dir):
    """Ensure the code passes chunk_size=8192 to iter_content (default in implementation)."""
    fake_resp = FakeResponse(status_code=200, chunks=[b"12345"])

    def fake_get(*args, **kwargs):
        return fake_resp

    with patch("download_mastr.requests.get", side_effect=fake_get):
        dest = temp_download_dir
        download_mastr.download_file(sample_url, str(dest))

    # Our FakeResponse records the chunk size it was called with
    assert fake_resp.iter_content_called_with == 8192


# Test that ensures the download function raises HTTPError for bad status codes
def test_download_propagates_http_errors(sample_url, temp_download_dir):
    """When HTTP status is >= 400, the function should raise requests.HTTPError."""
    with patch("download_mastr.requests.get", side_effect=_fake_get_factory(404, [])):
        try:
            download_mastr.download_file(sample_url, str(temp_download_dir))
            assert False, "Expected HTTPError to be raised"
        except requests.HTTPError:
            pass  # expected

# Test that ensures the download function returns the correct path and filename extraction
def test_returns_correct_path_and_filename_extraction(sample_url, temp_download_dir):
    """Function should return the absolute file path constructed from destination + basename(url)."""
    with patch("download_mastr.requests.get", side_effect=_fake_get_factory(200, [b"OK"])):
        result = download_mastr.download_file(sample_url, str(temp_download_dir))

    expected = temp_download_dir / os.path.basename(sample_url)
    assert Path(result) == expected and expected.exists()
