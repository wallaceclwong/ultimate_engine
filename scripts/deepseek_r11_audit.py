import asyncio
import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.append("/root/ultimate_engine")

from services.deep_dive_agent import DeepDiveAgent
from models.schemas import RaceCard

async def main():
    date_str = "2026-04-06"
    venue = "ST"
    race_no = 11

    print(f"\n[INFO] Starting Local DeepSeek-R1 Tactical Audit for {date_str} R{race_no}...")
    
    # Load directly from local VM filesystem to avoid GCS auth issues
    date_clean = date_str.replace("-", "")
    filename = f"/root/ultimate_engine/data/racecard_{date_clean}_R{race_no}.json"
    
    if not os.path.exists(filename):
        print(f"[ERROR] Racecard file {filename} not found.")
        return

    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)
        card = RaceCard.model_validate(data)

    agent = DeepDiveAgent()
    
    # Analyze the Top Pick (Saddle #1 - FALLON)
    print(f"\n--- AI WEATHER-AWARE TACTICAL REPORT: {card.horses[0].horse_name} (#1) ---")
    report = await agent.generate_report(card, card.horses[0].saddle_number)
    
    print("\n" + "="*60)
    print(report)
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
