import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.prediction_engine import PredictionEngine
from config.settings import Config

def create_tuning_jsonl(date_str, venue, output_file="data/tuning_dataset.jsonl"):
    """
    Scans local data for the given date/venue and creates a JSONL file
    for Vertex AI fine-tuning.
    """
    print("="*60)
    print(f"PREPARING TUNING DATA: {date_str} {venue}")
    print("="*60)
    
    engine = PredictionEngine()
    results_dir = Path("data/results")
    
    # We'll collect all results for this date
    result_files = list(results_dir.glob(f"results_{date_str}_{venue}_R*.json"))
    
    if not result_files:
        print(f"[ERROR] No results found for {date_str} {venue}")
        return
        
    print(f"Found {len(result_files)} races to process")
    
    count = 0
    with open(output_file, "a", encoding="utf-8") as out:
        for res_path in result_files:
            try:
                # Extract race info
                race_id = res_path.stem.replace("results_", "")
                parts = race_id.split("_")
                race_no = int(parts[2][1:]) # R1 -> 1
                
                # Load full data context (as if predicting)
                # Using engine.load_race_data to get complete context
                data = asyncio.run(engine.load_race_data(date_str, venue, race_no))
                
                if not data["racecard"] or not data["results"]:
                    continue
                
                # 1. Reconstruct the Prompt
                engine.bias_correction = {} # No bias for pure tuning data
                prompt = engine._construct_prompt(data)
                
                # 2. Reconstruct the "Ideal" Output
                # Find the winner
                winner_no = None
                winner_name = ""
                for h in data["results"].get("results", []):
                    if h.get("plc") == "1":
                        winner_no = h.get("horse_no")
                        winner_name = h.get("horse_name", f"Horse {winner_no}")
                        break
                
                if not winner_no:
                    continue
                
                # Construct ideal JSON response
                ideal_response = {
                    "confidence_score": 0.95,
                    "is_best_bet": True,
                    "recommended_bet": f"WIN {winner_no}",
                    "probabilities": {str(winner_no): 0.60}, # Focus on winner
                    "analysis_markdown": f"The model correctly identifies {winner_name} (#{winner_no}) as the superior athlete based on sectional consistency and class advantage."
                }
                
                # 3. Create JSONL entry (Gemini Tuning Format)
                entry = {
                    "contents": [
                        {"role": "user", "parts": [{"text": prompt}]},
                        {"role": "model", "parts": [{"text": json.dumps(ideal_response)}]}
                    ]
                }
                
                out.write(json.dumps(entry) + "\n")
                count += 1
                print(f"  Processed {race_id}")
                
            except Exception as e:
                print(f"  [ERROR] Race {res_path.name}: {e}")
                
    print("\n" + "="*60)
    print(f"SUCCESS! {count} examples added to {output_file}")
    print("="*60)

if __name__ == "__main__":
    # Example: Prepare data from the most recent meeting
    date = "2026-03-29"
    venue = "ST"
    create_tuning_jsonl(date, venue)
