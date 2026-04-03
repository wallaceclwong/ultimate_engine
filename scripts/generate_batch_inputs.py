import json
import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config
from services.prediction_engine import PredictionEngine

async def generate_batch_jsonl(output_file: str, start_year: int = 2018, end_year: int = 2023):
    """
    Scans data/results for races in the specified range and generates a JSONL file 
    compatible with Vertex AI Batch Prediction.
    """
    engine = PredictionEngine()
    results_dir = Path("data/results")
    predictions_dir = Path("data/predictions")
    
    if not results_dir.exists():
        print(f"Error: {results_dir} not found.")
        return

    print(f"Scanning for races from {start_year} to {end_year}...")
    
    # 1. Identify all results files in the range
    all_results = sorted(list(results_dir.glob("results_*.json")))
    target_races = []
    
    for rp in all_results:
        # Format: results_YYYY-MM-DD_VENUE_RN.json
        parts = rp.stem.split("_")
        if len(parts) < 3: continue
        
        date_str = parts[1] # YYYY-MM-DD
        venue = parts[2]
        race_no_str = parts[3].replace("R", "")
        
        try:
            year = int(date_str.split("-")[0])
            if start_year <= year <= end_year:
                # 2. Check if prediction already exists to avoid redundant work
                pred_file = predictions_dir / f"prediction_{date_str}_{venue}_R{race_no_str}.json"
                if not pred_file.exists():
                    target_races.append({
                        "date": date_str,
                        "venue": venue,
                        "race": int(race_no_str)
                    })
        except:
            continue

    print(f"Found {len(target_races)} races needing predictions.")

    # 3. Generate JSONL
    # Format for Vertex AI Batch: {"request": <GenerateContentRequest>}
    # Note: Using the PredictionEngine._construct_prompt logic
    
    with open(output_file, "w", encoding="utf-8") as f:
        for i, race in enumerate(target_races):
            if i % 100 == 0:
                print(f"Processing race {i}/{len(target_races)}...")
            
            try:
                # Load context data (results, analytical, etc.)
                data = await engine.load_race_data(race["date"], race["venue"], race["race"])
                
                # Check for hollow data
                racecard = data.get("racecard", {})
                horses = racecard.get("horses", [])
                
                if not horses:
                    print(f"Skipping {race['date']} R{race['race']} due to missing horse data.")
                    continue

                # Retrieve contextual weights (if any, defaults to 1.0)
                engine.bias_correction = engine.optimizer.get_weights(race["date"], race["venue"])
                
                # Build the prompt
                prompt_text = engine._construct_prompt(data)
                
                # Define probability properties for schema consistency
                racecard = data.get("racecard", {})
                horses = racecard.get("horses", [])
                prob_props = {
                    str(h.get("saddle_number") or h.get("horse_no")): {"type": "number"}
                    for h in horses
                }

                # Construct Vertex AI Request Object
                # Ref: https://cloud.google.com/vertex-ai/docs/generative-ai/multimodal/batch-prediction
                request = {
                    "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
                    "generation_config": {
                        "response_mime_type": "application/json",
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "confidence_score": {"type": "number"},
                                "is_best_bet": {"type": "boolean"},
                                "recommended_bet": {"type": "string"},
                                "probabilities": {
                                    "type": "object",
                                    "properties": prob_props,
                                    "required": list(prob_props.keys())
                                },
                                "analysis_markdown": {"type": "string"}
                            },
                        }
                    }
                }
                
                # Wrap for Batch JSONL
                batch_entry = {
                    "custom_id": f"{race['date']}_{race['venue']}_R{race['race']}",
                    "request": request
                }
                
                f.write(json.dumps(batch_entry) + "\n")
            except Exception as e:
                print(f"Error preparing {race['date']} R{race['race']}: {e}")

    print(f"\nSuccess! Generated {output_file} with {len(target_races)} requests.")
    print("Ready for Vertex AI Submission.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/batch_input_2018_2023.jsonl")
    args = parser.parse_args()
    
    asyncio.run(generate_batch_jsonl(args.output))
