import os
import sys
import json
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.firestore_service import FirestoreService
from config.settings import Config

def sync_predictions():
    print("="*60)
    print("CLOUD SYNC: LOCAL PREDICTIONS -> FIRESTORE")
    print("="*60)

    predictions_dir = Path("data/predictions")
    if not predictions_dir.exists():
        print(f"Error: Directory {predictions_dir} not found.")
        return

    service = FirestoreService()
    if not service.db:
        print("Error: Could not initialize Firestore. Check your credentials.")
        return

    # Find all JSON files
    files = list(predictions_dir.glob("*.json"))
    total_files = len(files)
    print(f"Found {total_files} local predictions.")

    batch_size = 50  # Firestore max batch size is 500, but 50 is safer for large docs
    current_batch = {}
    synced_count = 0

    for i, file_path in enumerate(files):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Use the race_id as document ID
            race_id = data.get("race_id")
            if not race_id:
                # Fallback: use filename if race_id is missing
                race_id = file_path.stem.replace("prediction_", "")
            
            current_batch[race_id] = data
            
            # If batch is full or it's the last file, sync
            if len(current_batch) >= batch_size or i == total_files - 1:
                service.batch_upsert(Config.COL_PREDICTIONS, current_batch)
                synced_count += len(current_batch)
                print(f"Progress: {synced_count}/{total_files} synced...")
                current_batch = {}
        
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")

    print("\n" + "="*60)
    print(f"SYNC COMPLETE: {synced_count} predictions processed.")
    print("="*60)

if __name__ == "__main__":
    sync_predictions()
