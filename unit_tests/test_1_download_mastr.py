"""
Unit tests for step1_download_mastr.download_file using pytest.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step1_download_mastr as download_mastr


@pytest.fixture
def temp_download_dir(tmp_path):
    return tmp_path


@pytest.fixture
def sample_url():
    return "https://example.com/sample_file.zip"


class FakeResponse:
    """A lightweight fake of requests.Response that supports the context manager protocol."""

    def __init__(self, status_code=200, chunks=None):
        self.status_code = status_code
        self._chunks = chunks or []
        self.iter_content_called_with = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code} error from fake response")

    def iter_content(self, chunk_size=8192):
        self.iter_content_called_with = chunk_size
        for chunk in self._chunks:
            yield chunk


def _fake_get_factory(status_code=200, chunks=None):
    """Return a fake requests.get implementation."""

    def _fake_get(url, stream=False, **kwargs):
        return FakeResponse(status_code=status_code, chunks=chunks)

    return _fake_get


def test_download_success_creates_folder_and_writes_file(temp_download_dir, sample_url, capsys):
    """Should create destination folder, write streamed bytes, and return the expected path."""
    dest = temp_download_dir / "raw"
    assert not dest.exists()

    chunks = [b"AAA", b"BBB", b"CCC"]

    with patch("scripts.step1_download_mastr.requests.get", side_effect=_fake_get_factory(200, chunks)) as mock_get:
        result_path = download_mastr.download_file(sample_url, str(dest))

    expected_path = dest / os.path.basename(sample_url)

    assert dest.exists()
    assert expected_path.exists()
    assert expected_path.read_bytes() == b"AAABBBCCC"
    assert result_path == str(expected_path)

    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert args[0] == sample_url
    assert kwargs["stream"] is True

    out = capsys.readouterr().out
    assert "Downloading" in out
    assert "completed" in out


def test_download_uses_existing_folder_without_recreating(temp_download_dir, sample_url, monkeypatch):
    """If destination folder already exists, os.makedirs should not be called."""
    dest = temp_download_dir / "already_there"
    dest.mkdir(parents=True, exist_ok=True)

    calls = {"makedirs": 0}
    original_makedirs = os.makedirs

    def fake_makedirs(path, exist_ok=False):
        calls["makedirs"] += 1
        original_makedirs(path, exist_ok=exist_ok)

    monkeypatch.setattr("scripts.step1_download_mastr.os.makedirs", fake_makedirs)

    with patch("scripts.step1_download_mastr.requests.get", side_effect=_fake_get_factory(200, [b"X"])):
        download_mastr.download_file(sample_url, str(dest))

    assert calls["makedirs"] == 0


def test_download_stream_chunk_size_is_8192(sample_url, temp_download_dir):
    """Should pass chunk_size=8192 to iter_content."""
    fake_resp = FakeResponse(status_code=200, chunks=[b"12345"])

    def fake_get(*args, **kwargs):
        return fake_resp

    with patch("scripts.step1_download_mastr.requests.get", side_effect=fake_get):
        download_mastr.download_file(sample_url, str(temp_download_dir))

    assert fake_resp.iter_content_called_with == 8192


def test_download_propagates_http_errors(sample_url, temp_download_dir):
    """Should raise requests.HTTPError for unsuccessful responses."""
    with patch("scripts.step1_download_mastr.requests.get", side_effect=_fake_get_factory(404, [])):
        with pytest.raises(requests.HTTPError):
            download_mastr.download_file(sample_url, str(temp_download_dir))


def test_download_does_not_create_file_when_http_error(sample_url, temp_download_dir):
    """Should not leave a file behind if the request fails before writing starts."""
    expected_path = temp_download_dir / os.path.basename(sample_url)

    with patch("scripts.step1_download_mastr.requests.get", side_effect=_fake_get_factory(404, [])):
        with pytest.raises(requests.HTTPError):
            download_mastr.download_file(sample_url, str(temp_download_dir))

    assert not expected_path.exists()


def test_returns_correct_path_and_filename_extraction(sample_url, temp_download_dir):
    """Should return destination + basename(url)."""
    with patch("scripts.step1_download_mastr.requests.get", side_effect=_fake_get_factory(200, [b"OK"])):
        result = download_mastr.download_file(sample_url, str(temp_download_dir))

    expected = temp_download_dir / os.path.basename(sample_url)
    assert Path(result) == expected
    assert expected.exists()


def test_download_handles_empty_chunks(sample_url, temp_download_dir):
    """Should tolerate empty chunks and still write the non-empty content."""
    chunks = [b"A", b"", b"B", b"", b"C"]

    with patch("scripts.step1_download_mastr.requests.get", side_effect=_fake_get_factory(200, chunks)):
        result = download_mastr.download_file(sample_url, str(temp_download_dir))

    assert Path(result).read_bytes() == b"ABC"