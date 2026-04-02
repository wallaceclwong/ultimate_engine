import os
import json
import sys
from datetime import datetime
from google.cloud import bigquery
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.bigquery_service import BigQueryService

def backfill_results():
    bq = BigQueryService()
    results_dir = Path("data/results")
    if not results_dir.exists():
        print("[ERROR] Results directory not found.")
        return

    rows_to_insert = []
    for file_path in results_dir.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # Basic race info
                race_id = data.get("race_id")
                date_str = data.get("date")
                if not date_str: continue
                
                # Transform to BigQuery row
                row = {
                    "race_id": race_id,
                    "date": date_str,
                    "venue": data.get("venue"),
                    "race_no": data.get("race_no"),
                    "distance": data.get("distance"),
                    "going": data.get("going"),
                    "course": data.get("course"),
                    "horse_results": [],
                    "sectional_times": data.get("sectional_times", []),
                    "created_at": datetime.utcnow().isoformat()
                }
                
                # Horse results
                for h in data.get("results", []):
                    row["horse_results"].append({
                        "pos": h.get("pos"),
                        "horse_no": h.get("horse_no"),
                        "horse_name": h.get("horse_name"),
                        "jockey": h.get("jockey"),
                        "trainer": h.get("trainer"),
                        "win_odds": h.get("win_odds"),
                        "draw": h.get("draw"),
                        "weight": h.get("weight")
                    })
                
                rows_to_insert.append(row)
        except Exception as e:
            print(f"[ERROR] Failed to process {file_path.name}: {e}")

    if rows_to_insert:
        print(f"[INFO] Inserting {len(rows_to_insert)} races into BigQuery...")
        table_id = f"{bq.dataset_id}.race_results"
        errors = bq.client.insert_rows_json(table_id, rows_to_insert)
        if errors:
            print(f"[ERROR] Failed to insert rows: {errors}")
        else:
            print(f"[SUCCESS] Backfilled {len(rows_to_insert)} races to BigQuery.")

if __name__ == "__main__":
    backfill_results()
