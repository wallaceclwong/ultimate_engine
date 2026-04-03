import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.storage_service import StorageService
from config.settings import Config

def sync_all():
    storage = StorageService()
    predictions_dir = Path("data/predictions")
    
    if not predictions_dir.exists():
        print("No predictions found to sync.")
        return

    files = list(predictions_dir.glob("*.json"))
    print(f"Syncing {len(files)} predictions to gs://{Config.GCS_BUCKET_NAME}...")

    success_count = 0
    for f in files:
        race_id = f.stem.replace("prediction_", "")
        if storage.upload_prediction(race_id, str(f)):
            success_count += 1
            if success_count % 50 == 0:
                print(f"Synced {success_count} files...")
        else:
            print(f"Failed to sync {f.name}")

    print(f"Sync complete. Total: {success_count}/{len(files)}")

if __name__ == "__main__":
    sync_all()
