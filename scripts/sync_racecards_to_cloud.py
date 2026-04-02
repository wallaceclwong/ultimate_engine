import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.firestore_service import FirestoreService
from config.settings import Config

def sync_racecards():
    print("="*60)
    print("CLOUD SYNC: LOCAL RACECARDS -> FIRESTORE")
    print("="*60)

    # In your project, racecards seem to be in data/ or root data
    # Based on server.py: DATA_DIR / f"racecard_{date_compact}_R{race_no}.json"
    data_dir = Path("data")
    if not data_dir.exists():
        print(f"Error: Directory {data_dir} not found.")
        return

    service = FirestoreService()
    if not service.db:
        print("Error: Could not initialize Firestore.")
        return

    # Find all racecard JSON files
    files = list(data_dir.glob("racecard_*.json"))
    total_files = len(files)
    print(f"Found {total_files} local racecards.")

    batch_size = 50
    current_batch = {}
    synced_count = 0

    for i, file_path in enumerate(files):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Use the format YYYYMMDD_RX as document ID to match server.py fallback
            # Filename is usually racecard_YYYYMMDD_RX.json
            doc_id = file_path.stem.replace("racecard_", "")
            
            current_batch[doc_id] = data
            
            if len(current_batch) >= batch_size or i == total_files - 1:
                service.batch_upsert(Config.COL_RACECARDS, current_batch)
                synced_count += len(current_batch)
                print(f"Progress: {synced_count}/{total_files} synced...")
                current_batch = {}
        
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")

    print("\n" + "="*60)
    print(f"SYNC COMPLETE: {synced_count} racecards processed.")
    print("="*60)

if __name__ == "__main__":
    sync_racecards()
