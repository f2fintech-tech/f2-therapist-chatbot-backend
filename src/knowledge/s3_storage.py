"""
Handle uploading and downloading knowledge base from AWS S3
"""

import boto3
import hashlib
import json
from datetime import datetime
from pathlib import Path
import logging
import os
from botocore.exceptions import ClientError

# Logger setup for tracking events, errors, and debugging
logger = logging.getLogger(__name__)


def _validate_path_parameter(path: str, allow_relative: bool = True) -> bool:
    """
    Validate path parameter to prevent directory traversal attacks.

    This function ensures that the given path is safe to use and does not allow:
    - Absolute paths (like /etc/passwd)
    - Directory traversal (../)
    - Home directory shortcuts (~)
    - Null byte injection

    Args:
        path: Path to validate
        allow_relative: Whether to allow relative paths

    Returns:
        True if path is safe, False otherwise
    """

    # Check if path exists and is a string
    if not path or not isinstance(path, str):
        return False

    # Prevent absolute paths (security risk)
    if path.startswith('/'):
        return False

    # Prevent directory traversal attacks and home directory access
    if '..' in path or path.startswith('~'):
        return False

    # Prevent null byte injection attacks
    if '\x00' in path:
        return False

    return True


class S3StorageManager:
    def __init__(self, bucket_name: str = "f2fintech-knowledge-base", region: str = "ap-south-1"):
        """
        Initialize S3 connection.

        This sets up the AWS S3 client and verifies that the bucket exists.

        Args:
            bucket_name: S3 bucket name
            region: AWS region
        """

        self.bucket_name = bucket_name
        self.region = region

        # Create S3 client using boto3
        self.s3_client = boto3.client('s3', region_name=region)

        # Check if bucket exists and is accessible
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Connected to S3 bucket: {bucket_name}")
        except ClientError as e:
            logger.error(f"Failed to connect to S3 bucket: {e}")
            raise

    def upload_file(self, local_path: str, s3_path: str):
        """
        Upload a local file to S3.

        Args:
            local_path: Local file path (example: src/data/raw/file.json)
            s3_path: Destination path inside S3 (example: raw/file.json)
        """

        # Validate S3 path for safety
        """if not _validate_path_parameter(s3_path):
            logger.error(f"Invalid S3 path: {s3_path}")
            return False

        try:
            # Upload file to S3 bucket
            self.s3_client.upload_file(local_path, self.bucket_name, s3_path)

            logger.info(f"Uploaded {local_path} to s3://{self.bucket_name}/{s3_path}")
            return True

        except ClientError as e:
            logger.error(f"Failed to upload {local_path}: {e}")
            return False"""

    def download_file(self, s3_path: str, local_path: str):
        """
        Download a file from S3 to local system.

        Args:
            s3_path: Path inside S3 (example: raw/file.json)
            local_path: Destination local path (example: src/data/raw/file.json)
        """

        # Validate S3 path
        if not _validate_path_parameter(s3_path):
            logger.error(f"Invalid S3 path: {s3_path}")
            return False

        try:
            # Ensure local directory exists before downloading
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)

            # Download file from S3
            self.s3_client.download_file(self.bucket_name, s3_path, local_path)

            logger.info(f"Downloaded s3://{self.bucket_name}/{s3_path} to {local_path}")
            return True

        except ClientError as e:
            logger.error(f"Failed to download {s3_path}: {e}")
            return False

    def _raw_sync_state_path(self):
        """Store raw download state next to the local raw files."""
        return Path("src/data/raw/.s3_sync_state.json")

    def _load_raw_sync_state(self):
        """Load the last known S3 signatures for raw files."""
        state_path = self._raw_sync_state_path()
        if not state_path.exists():
            return {"files": {}, "last_sync": None}

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            if not isinstance(state, dict):
                return {"files": {}, "last_sync": None}
            state.setdefault("files", {})
            state.setdefault("last_sync", None)
            return state
        except Exception:
            logger.warning(f"Could not read raw sync state from {state_path}; starting fresh")
            return {"files": {}, "last_sync": None}

    def _save_raw_sync_state(self, state):
        """Persist the latest S3 signatures for raw files."""
        state_path = self._raw_sync_state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _normalize_etag(etag):
        """Remove S3 quotes around ETag values."""
        if not etag:
            return ""
        return str(etag).strip('"')

    @staticmethod
    def _local_file_hash(file_path: Path):
        """Compute an MD5 hash for a local file so we can compare it to S3 ETags."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def list_objects(self, prefix: str = ""):
        """
        List objects in S3 using pagination.

        This returns metadata so incremental sync can decide whether a file
        is new or changed before downloading it.
        """

        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            objects = []

            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for obj in page.get("Contents", []):
                    objects.append({
                        "Key": obj.get("Key", ""),
                        "ETag": obj.get("ETag", ""),
                        "Size": obj.get("Size", 0),
                        "LastModified": obj.get("LastModified"),
                    })

            logger.info(f"Objects in s3://{self.bucket_name}/{prefix}: {[item['Key'] for item in objects]}")
            return objects

        except ClientError as e:
            logger.error(f"Failed to list objects: {e}")
            return []

    def list_files(self, prefix: str = ""):
        """
        List files in S3 using a prefix.

        Note:
        S3 does not have real directories, only "prefixes" that simulate folders.

        Args:
            prefix: Example "raw/" or "processed/"

        Returns:
            List of file keys
        """

        return [obj["Key"] for obj in self.list_objects(prefix=prefix)]

    def sync_raw_to_s3(self):
        """
        Upload all files from local raw directory to S3.

        Local directory: src/data/raw
        S3 destination: raw/
        """

        raw_dir = Path("src/data/raw")

        # Check if directory exists
        if not raw_dir.exists():
            logger.error(f"Raw data directory not found: {raw_dir}")
            return False

        success = True

        # Loop through all files in directory
        for file_path in raw_dir.glob("*"):
            if file_path.is_file():
                s3_path = f"raw/{file_path.name}"

                # Upload each file
                if not self.upload_file(str(file_path), s3_path):
                    success = False

        if success:
            logger.info("Successfully synced raw files to S3")

        return success

    def sync_processed_to_s3(self):
        """
        Upload processed files to S3.

        Local directory: src/data/processed
        S3 destination: processed/
        """

        processed_dir = Path("src/data/processed")

        if not processed_dir.exists():
            logger.warning(f"Processed directory not found: {processed_dir}")
            return False

        success = True

        for file_path in processed_dir.glob("*"):
            if file_path.is_file():
                s3_path = f"processed/{file_path.name}"

                if not self.upload_file(str(file_path), s3_path):
                    success = False

        if success:
            logger.info("Successfully synced processed files to S3")

        return success

    def download_raw_from_s3(self):
        """
        Download only new or changed raw files from S3.

        The pipeline keeps any local file that already matches the remote S3
        object, so a collaborator can upload just a few updates without forcing
        a full re-download.
        """

        return self.download_raw_incremental_from_s3()

    def download_raw_incremental_from_s3(self):
        """
        Download only raw files that are missing or have changed in S3.

        The check uses two signals:
        - Local file MD5 vs S3 ETag when the object is a simple upload.
        - A small local sync state file for bookkeeping and repeat runs.
        """

        raw_dir = Path("src/data/raw")
        raw_dir.mkdir(parents=True, exist_ok=True)

        objects = self.list_objects(prefix="raw/")
        sync_state = self._load_raw_sync_state()
        tracked_files = sync_state.setdefault("files", {})

        success = True
        downloaded = 0
        skipped = 0

        for obj in objects:
            s3_file = obj.get("Key", "")

            if s3_file == "raw/":
                # S3 sometimes returns a placeholder folder key; skip it.
                continue

            file_name = s3_file.split("/")[-1]
            if not file_name:
                continue

            local_path = raw_dir / file_name
            remote_signature = {
                "etag": self._normalize_etag(obj.get("ETag", "")),
                "size": obj.get("Size", 0),
                "last_modified": obj.get("LastModified").isoformat() if obj.get("LastModified") else None,
            }

            # If the local file already matches the S3 object, skip the download.
            local_matches_remote = False
            if local_path.exists() and remote_signature["etag"] and "-" not in remote_signature["etag"]:
                local_matches_remote = self._local_file_hash(local_path) == remote_signature["etag"]
            elif local_path.exists():
                previous_signature = tracked_files.get(s3_file)
                local_matches_remote = previous_signature == remote_signature

            if local_matches_remote:
                tracked_files[s3_file] = remote_signature
                skipped += 1
                continue

            # Only download files that are new or actually changed.
            if self.download_file(s3_file, str(local_path)):
                tracked_files[s3_file] = remote_signature
                downloaded += 1
            else:
                success = False

        sync_state["last_sync"] = datetime.utcnow().isoformat() + "Z"
        sync_state["files"] = tracked_files
        self._save_raw_sync_state(sync_state)

        if success:
            logger.info(
                f"Successfully downloaded raw files from S3 (downloaded={downloaded}, skipped={skipped})"
            )

        return success

    def download_processed_from_s3(self):
        """
        Download processed files from S3.
        """

        processed_dir = Path("src/data/processed")
        processed_dir.mkdir(parents=True, exist_ok=True)

        files = self.list_files(prefix="processed/")

        success = True

        for s3_file in files:
            if s3_file != "processed/":
                file_name = s3_file.split("/")[-1]

                if file_name:
                    local_path = f"src/data/processed/{file_name}"

                    if not self.download_file(s3_file, local_path):
                        success = False

        if success:
            logger.info("Successfully downloaded processed files from S3")

        return success

    def sync_all(self):
        """
        Sync both raw and processed files to S3.
        """

        logger.info("Starting full sync to S3...")

        raw_success = self.sync_raw_to_s3()
        processed_success = self.sync_processed_to_s3()

        if raw_success and processed_success:
            logger.info("Full sync to S3 complete!")
            return True
        else:
            logger.error("Some files failed to sync")
            return False

    def download_all(self):
        """
        Download both raw and processed files from S3.
        """

        logger.info("Starting full download from S3...")

        raw_success = self.download_raw_from_s3()
        processed_success = self.download_processed_from_s3()

        if raw_success and processed_success:
            logger.info("Full download from S3 complete!")
            return True
        else:
            logger.error("Some files failed to download")
            return False

    def delete_file(self, s3_path: str):
        """
        Delete a file from S3.
        """

        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_path)

            logger.info(f"Deleted s3://{self.bucket_name}/{s3_path}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete {s3_path}: {e}")
            return False

    def get_s3_url(self, s3_path: str, expiration: int = 3600):
        """
        Generate a presigned URL.

        This allows temporary access to a private S3 file.

        Args:
            s3_path: File path in S3
            expiration: Time in seconds before URL expires
        """

        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_path},
                ExpiresIn=expiration
            )

            logger.info(f"Generated presigned URL for {s3_path}")
            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None


# CLI Commands
if __name__ == "__main__":
    import sys

    # Initialize manager
    manager = S3StorageManager()

    # If no command is passed
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m src.knowledge.s3_storage upload-raw")
        print("  python -m src.knowledge.s3_storage upload-processed")
        print("  python -m src.knowledge.s3_storage download-raw")
        print("  python -m src.knowledge.s3_storage download-processed")
        print("  python -m src.knowledge.s3_storage sync-all")
        print("  python -m src.knowledge.s3_storage download-all")
        print("  python -m src.knowledge.s3_storage list [prefix]")
        print("  python -m src.knowledge.s3_storage delete [s3_path]")
        print("  python -m src.knowledge.s3_storage get-url [s3_path]")
        sys.exit(1)

    command = sys.argv[1]

    # Map CLI commands to methods
    if command == "upload-raw":
        manager.sync_raw_to_s3()

    elif command == "upload-processed":
        manager.sync_processed_to_s3()

    elif command == "download-raw":
        manager.download_raw_from_s3()

    elif command == "download-processed":
        manager.download_processed_from_s3()

    elif command == "sync-all":
        manager.sync_all()

    elif command == "download-all":
        manager.download_all()

    elif command == "list":
        prefix = sys.argv[2] if len(sys.argv) > 2 else ""
        manager.list_files(prefix)

    elif command == "delete":
        if len(sys.argv) < 3:
            print("Usage: python -m src.knowledge.s3_storage delete [s3_path]")
        else:
            s3_path = sys.argv[2]
            manager.delete_file(s3_path)

    elif command == "get-url":
        if len(sys.argv) < 3:
            print("Usage: python -m src.knowledge.s3_storage get-url [s3_path]")
        else:
            s3_path = sys.argv[2]
            url = manager.get_s3_url(s3_path)

            if url:
                print(f"Presigned URL: {url}")

    else:
        print(f"Unknown command: {command}")
