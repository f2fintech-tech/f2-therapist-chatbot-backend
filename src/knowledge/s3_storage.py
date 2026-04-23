"""
Handle uploading and downloading knowledge base from AWS S3
"""

import boto3
from pathlib import Path
import logging
import os
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class S3StorageManager:
    def __init__(self, bucket_name: str = "f2-fintech-kb", region: str = "us-east-1"):
        """
        Initialize S3 connection.
        
        Args:
            bucket_name: S3 bucket name
            region: AWS region
        """
        self.bucket_name = bucket_name
        self.region = region
        
        # Initialize S3 client
        self.s3_client = boto3.client('s3', region_name=region)
        
        # Verify bucket exists
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
            local_path: Path to local file (e.g., "src/data/raw/scenarios_raw.json")
            s3_path: Path in S3 (e.g., "raw/scenarios_raw.json")
        """
        try:
            self.s3_client.upload_file(local_path, self.bucket_name, s3_path)
            logger.info(f"Uploaded {local_path} to s3://{self.bucket_name}/{s3_path}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload {local_path}: {e}")
            return False
    
    def download_file(self, s3_path: str, local_path: str):
        """
        Download a file from S3 to local.
        
        Args:
            s3_path: Path in S3 (e.g., "raw/scenarios_raw.json")
            local_path: Path to save locally (e.g., "src/data/raw/scenarios_raw.json")
        """
        try:
            # Create local directory if needed
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            
            self.s3_client.download_file(self.bucket_name, s3_path, local_path)
            logger.info(f"Downloaded s3://{self.bucket_name}/{s3_path} to {local_path}")
            return True
        except ClientError as e:
            logger.error(f"Failed to download {s3_path}: {e}")
            return False
    
    def list_files(self, prefix: str = ""):
        """
        List all files in an S3 directory.
        
        Args:
            prefix: S3 prefix (e.g., "raw/" or "processed/")
        
        Returns:
            List of file names
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            files = []
            if 'Contents' in response:
                files = [obj['Key'] for obj in response['Contents']]
            
            logger.info(f"Files in s3://{self.bucket_name}/{prefix}: {files}")
            return files
        except ClientError as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    def sync_raw_to_s3(self):
        """Upload raw data files to S3."""
        raw_dir = Path("src/data/raw")
        
        if not raw_dir.exists():
            logger.error(f"Raw data directory not found: {raw_dir}")
            return False
        
        success = True
        for file_path in raw_dir.glob("*"):
            if file_path.is_file():
                s3_path = f"raw/{file_path.name}"
                if not self.upload_file(str(file_path), s3_path):
                    success = False
        
        if success:
            logger.info("Successfully synced raw files to S3")
        return success
    
    def sync_processed_to_s3(self):
        """Upload processed data files to S3."""
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
        """Download raw data files from S3."""
        raw_dir = Path("src/data/raw")
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        files = self.list_files(prefix="raw/")
        
        success = True
        for s3_file in files:
            if s3_file != "raw/":  # Skip directory entry
                file_name = s3_file.split("/")[-1]
                if file_name:
                    local_path = f"src/data/raw/{file_name}"
                    if not self.download_file(s3_file, local_path):
                        success = False
        
        if success:
            logger.info("Successfully downloaded raw files from S3")
        return success
    
    def download_processed_from_s3(self):
        """Download processed data files from S3."""
        processed_dir = Path("src/data/processed")
        processed_dir.mkdir(parents=True, exist_ok=True)
        
        files = self.list_files(prefix="processed/")
        
        success = True
        for s3_file in files:
            if s3_file != "processed/":  # Skip directory entry
                file_name = s3_file.split("/")[-1]
                if file_name:
                    local_path = f"src/data/processed/{file_name}"
                    if not self.download_file(s3_file, local_path):
                        success = False
        
        if success:
            logger.info("Successfully downloaded processed files from S3")
        return success
    
    def sync_all(self):
        """Sync both raw and processed files to S3."""
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
        """Download both raw and processed files from S3."""
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
        """Delete a file from S3."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_path)
            logger.info(f"Deleted s3://{self.bucket_name}/{s3_path}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete {s3_path}: {e}")
            return False
    
    def get_s3_url(self, s3_path: str, expiration: int = 3600):
        """
        Generate a presigned URL for sharing.
        
        Args:
            s3_path: Path in S3
            expiration: URL expiration time in seconds (default 1 hour)
        
        Returns:
            Presigned URL
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
    
    manager = S3StorageManager()
    
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