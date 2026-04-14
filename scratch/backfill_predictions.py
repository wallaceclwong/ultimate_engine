import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from services.prediction_engine import PredictionEngine

async def backfill(date_str, venue, races):
    engine = PredictionEngine()
    print(f"Starting backfill for {date_str} at {venue}")
    for r in range(1, races + 1):
        print(f"Generating prediction for R{r}...")
        try:
            await engine.generate_prediction(date_str, venue, r)
        except Exception as e:
            print(f"Error for R{r}: {e}")

if __name__ == "__main__":
    date = sys.argv[1] # e.g. 2026-04-08
    venue = sys.argv[2] # e.g. HV
    races = int(sys.argv[3]) # e.g. 9
    asyncio.run(backfill(date, venue, races))
