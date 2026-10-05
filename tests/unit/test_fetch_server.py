"""Security regression tests for the llama.cpp archive extractor."""

from __future__ import annotations

import io
import zipfile

import pytest

from scripts.fetch_server import safe_extract


def _zip_with(name: str) -> io.BytesIO:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(name, "owned")
    data.seek(0)
    return data


def test_safe_extract_rejects_zip_slip(tmp_path):
    with pytest.raises(ValueError, match="unsafe archive path"):
        with zipfile.ZipFile(_zip_with("../escaped.txt")) as archive:
            safe_extract(archive, tmp_path)


def test_safe_extract_allows_nested_files(tmp_path):
    with zipfile.ZipFile(_zip_with("bin/llama-server.exe")) as archive:
        safe_extract(archive, tmp_path)
    assert (tmp_path / "bin" / "llama-server.exe").read_text() == "owned"
