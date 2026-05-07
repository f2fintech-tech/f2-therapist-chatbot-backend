"""
Tests for incremental raw-file downloads from S3.

These tests use a fake boto3 client so we can prove the download step skips
files that already match S3 and only fetches files that are missing.
"""

import hashlib
from pathlib import Path

import pytest

from src.knowledge import s3_storage


def _md5(text: str) -> str:
    """Return the MD5 hash S3 uses for a simple upload ETag."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class FakePaginator:
    """Simple paginator that returns one page of S3 objects."""

    def __init__(self, contents):
        self.contents = contents

    def paginate(self, Bucket, Prefix):
        yield {"Contents": self.contents}


class FakeS3Client:
    """Tiny S3 client stub for download tests."""

    def __init__(self, contents, downloads):
        self.contents = contents
        self.downloads = downloads

    def head_bucket(self, Bucket):
        return {}

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return FakePaginator(self.contents)

    def download_file(self, bucket, key, local_path):
        self.downloads.append((bucket, key, local_path))
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        Path(local_path).write_text(f"downloaded:{key}", encoding="utf-8")


@pytest.fixture
def temp_working_dir(tmp_path, monkeypatch):
    """Run the test with a temporary working directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_incremental_raw_download_skips_matching_file(temp_working_dir, monkeypatch):
    """If local content already matches S3, the file should not be downloaded again."""
    raw_dir = temp_working_dir / "src/data/raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    local_content = "{""id"": 1, ""name"": ""alpha""}"
    local_file = raw_dir / "faqs_raw.json"
    local_file.write_text(local_content, encoding="utf-8")

    downloads = []
    remote_objects = [
        {
            "Key": "raw/faqs_raw.json",
            "ETag": f'"{_md5(local_content)}"',
            "Size": len(local_content),
            "LastModified": None,
        }
    ]

    fake_client = FakeS3Client(remote_objects, downloads)
    monkeypatch.setattr(s3_storage.boto3, "client", lambda *args, **kwargs: fake_client)

    manager = s3_storage.S3StorageManager(bucket_name="demo-bucket", region="us-east-1")
    assert manager.download_raw_from_s3() is True
    assert downloads == []


def test_incremental_raw_download_fetches_missing_file(temp_working_dir, monkeypatch):
    """If a file is missing locally, the downloader should fetch only that file."""
    downloads = []
    remote_objects = [
        {
            "Key": "raw/scenarios_raw.json",
            "ETag": '"1234567890abcdef1234567890abcdef"',
            "Size": 42,
            "LastModified": None,
        }
    ]

    fake_client = FakeS3Client(remote_objects, downloads)
    monkeypatch.setattr(s3_storage.boto3, "client", lambda *args, **kwargs: fake_client)

    manager = s3_storage.S3StorageManager(bucket_name="demo-bucket", region="us-east-1")
    assert manager.download_raw_from_s3() is True

    assert len(downloads) == 1
    bucket, key, local_path = downloads[0]
    assert bucket == "demo-bucket"
    assert key == "raw/scenarios_raw.json"
    assert Path(local_path).exists()
