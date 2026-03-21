import zipfile

import pytest

import zip_service


def test_extract_zip_archive_allows_safe_member(tmp_path):
    zip_path = tmp_path / "safe.zip"
    out_dir = tmp_path / "out"

    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("chapter1.mp3", b"abc123")

    zip_service.extract_zip_archive(str(zip_path), str(out_dir))

    assert (out_dir / "chapter1.mp3").read_bytes() == b"abc123"


def test_extract_zip_archive_rejects_path_traversal(tmp_path):
    zip_path = tmp_path / "evil.zip"

    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../escape.txt", b"boom")

    with pytest.raises(zip_service.UnsafeZipArchiveError, match="path traversal"):
        zip_service.extract_zip_archive(str(zip_path), str(tmp_path / "out"))
