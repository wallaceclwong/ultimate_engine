import os
from google.cloud import storage
from config.settings import Config
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        self.client = storage.Client(project=Config.PROJECT_ID)
        self.bucket_name = Config.GCS_BUCKET_NAME
        self.bucket = self.client.bucket(self.bucket_name)

    async def upload_file(self, local_path: str, blob_name: str):
        """Uploads a file to the bucket."""
        try:
            if not os.path.exists(local_path):
                logger.error(f"Local file not found: {local_path}")
                return False

            blob = self.bucket.blob(blob_name)
            blob.upload_from_filename(local_path)
            logger.info(f"Successfully uploaded {local_path} to gs://{self.bucket_name}/{blob_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload to GCS: {e}")
            return False

    def upload_prediction(self, race_id: str, local_path: str):
        """Convenience method for predictions."""
        blob_name = f"predictions/{race_id}.json"
        # We run this synchronously in the background task for now
        return self.upload_file_sync(local_path, blob_name)

    def upload_file_sync(self, local_path: str, blob_name: str):
        """Synchronous version for background tasks."""
        try:
            blob = self.bucket.blob(blob_name)
            blob.upload_from_filename(local_path)
            return True
        except Exception as e:
            logger.error(f"GCS Sync Error: {e}")
            return False
