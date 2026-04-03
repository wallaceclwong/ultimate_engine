import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.firestore_service import FirestoreService
from config.settings import Config

def sync_collection(collection_name, local_dir_name, file_prefix):
    print("\n" + "="*60)
    print(f"SYNCING: {local_dir_name} -> {collection_name}")
    print("="*60)
    
    local_dir = Path("data") / local_dir_name
    if not local_dir.exists():
        print(f"[SKIP] Directory {local_dir} not found")
        return
    
    service = FirestoreService()
    if not service.db:
        print("[ERROR] Firestore not initialized")
        return
    
    # Get all json files
    files = list(local_dir.glob(f"{file_prefix}*.json"))
    total = len(files)
    print(f"Found {total} files to sync")
    
    if total == 0:
        return
        
    batch_size = 50
    current_batch = {}
    synced = 0
    
    for i, file_path in enumerate(files):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Document ID is the filename stem, removing prefix if needed
            doc_id = file_path.stem
            if file_prefix and doc_id.startswith(file_prefix):
                # Only remove prefix if it's explicitly part of the meeting/race ID
                # For results_2026-03-29_ST_R1.json -> 2026-03-29_ST_R1
                if file_prefix.endswith('_'):
                    doc_id = doc_id[len(file_prefix):]
            
            current_batch[doc_id] = data
            
            # Batch upsert every X files
            if len(current_batch) >= batch_size or i == total - 1:
                success = service.batch_upsert(collection_name, current_batch)
                if success:
                    synced += len(current_batch)
                    print(f"  Progress: {synced}/{total} synced")
                else:
                    print(f"  [ERROR] Batch sync failed for {len(current_batch)} files")
                current_batch = {}
                
        except Exception as e:
            print(f"  [ERROR] Processing {file_path.name}: {e}")
            
    print(f"\n[OK] Completed {collection_name}: {synced} documents synced")

def main():
    print("="*60)
    print("FORCE FULL CLOUD SYNC")
    print("="*60)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Predictions
    sync_collection(Config.COL_PREDICTIONS, "predictions", "prediction_")
    
    # 2. Results
    sync_collection(Config.COL_RESULTS, "results", "results_")
    
    # 3. Analytical Data
    sync_collection(Config.COL_ANALYTICAL, "analytical", "")
    
    # 4. Market Odds
    sync_collection(Config.COL_ODDS, "odds", "")
    
    # 5. Weather Intel
    sync_collection(Config.COL_WEATHER, "weather", "")
    
    print("\n" + "="*60)
    print("ALL SYNC OPERATIONS COMPLETE")
    print("="*60)

if __name__ == "__main__":
    main()
