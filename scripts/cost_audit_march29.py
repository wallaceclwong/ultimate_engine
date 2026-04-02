import os
import sys
import json
import asyncio
from pathlib import Path
from google import genai

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.prediction_engine import PredictionEngine
from config.settings import Config

# Gemini 2.5 Pro Pricing (Vertex AI) - USD
PRICING = {
    "input_per_1k": 0.00125,
    "output_per_1k": 0.00375
}

async def audit_meeting_cost(date_str, venue):
    print("="*60)
    print(f"COST AUDIT: {date_str} {venue} MEETING")
    print("="*60)
    
    engine = PredictionEngine()
    total_input_tokens = 0
    total_output_tokens = 0 # Estimating based on actual prediction files
    
    # We'll check races 1-11
    races_found = 0
    
    for race_no in range(1, 13):
        try:
            # 1. Load data & Construct local prompt
            data = await engine.load_race_data(date_str, venue, race_no)
            if not data["racecard"]:
                continue
                
            races_found += 1
            
            # 2. Get contextual weights
            engine.bias_correction = engine.optimizer.get_weights(date_str, venue)
            prompt = engine._construct_prompt(data)
            
            # 3. Count exact input tokens
            response = engine.client.models.count_tokens(
                model=Config.GEMINI_MODEL,
                contents=prompt
            )
            input_tokens = response.total_tokens
            total_input_tokens += input_tokens
            
            # 4. Check actual output tokens from existing prediction file (if exists)
            pred_file = Path(f"data/predictions/prediction_{date_str}_{venue}_R{race_no}.json")
            output_tokens = 600 # Default estimate
            if pred_file.exists():
                with open(pred_file, 'r', encoding='utf-8') as f:
                    pred_data = f.read()
                # Very rough token estimate for output (1 token ~= 4 chars)
                output_tokens = len(pred_data) // 4
            
            total_output_tokens += output_tokens
            
            print(f"Race {race_no}: {input_tokens} Input | ~{output_tokens} Output")
            
        except Exception as e:
            print(f"Race {race_no}: [ERROR] {e}")

    if races_found == 0:
        print("\n[ERROR] No race data found for this date/venue.")
        return

    # Calculations
    input_cost = (total_input_tokens / 1000) * PRICING["input_per_1k"]
    output_cost = (total_output_tokens / 1000) * PRICING["output_per_1k"]
    total_cost = input_cost + output_cost
    
    print("\n" + "="*60)
    print("MEETING SUMMARY")
    print("="*60)
    print(f"Total Races: {races_found}")
    print(f"Total Input: {total_input_tokens} tokens (${input_cost:.4f})")
    print(f"Total Output: ~{total_output_tokens} tokens (${output_cost:.4f})")
    print(f"\nTOTAL COST: ${total_cost:.4f} USD")
    print("="*60)
    print(f"Cost per Race: ${total_cost/races_found:.4f}")
    print(f"Estimated Monthly (8 meetings): ${total_cost * 8:.2f} USD")
    print("="*60)

if __name__ == "__main__":
    date = "2026-03-29"
    venue = "ST"
    asyncio.run(audit_meeting_cost(date, venue))
