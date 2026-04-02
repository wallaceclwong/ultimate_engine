import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.firestore_service import FirestoreService
from config.settings import Config

def sync_collection(name, directory):
    print("="*60)
    print(f"CLOUD SYNC: LOCAL {name.upper()} -> FIRESTORE")
    print("="*60)

    source_dir = Path("data") / directory
    if not source_dir.exists():
        print(f"Error: Directory {source_dir} not found.")
        return

    service = FirestoreService()
    if not service.db:
        print("Error: Could not initialize Firestore.")
        return

    files = list(source_dir.glob("*.json"))
    total_files = len(files)
    print(f"Found {total_files} local files in {name}.")

    batch_size = 50
    current_batch = {}
    synced_count = 0

    for i, file_path in enumerate(files):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Use filename as document ID
            doc_id = file_path.stem
            current_batch[doc_id] = data
            
            if len(current_batch) >= batch_size or i == total_files - 1:
                service.batch_upsert(name, current_batch)
                synced_count += len(current_batch)
                print(f"Progress: {synced_count}/{total_files} synced...")
                current_batch = {}
        
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")

    print("\n" + "="*60)
    print(f"SYNC COMPLETE: {synced_count} {name} documents processed.")
    print("="*60)

if __name__ == "__main__":
    # Sync remaining collections
    sync_collection(Config.COL_ANALYTICAL, "analytical")
    sync_collection(Config.COL_ODDS, "odds")
    sync_collection(Config.COL_WEATHER, "weather")
