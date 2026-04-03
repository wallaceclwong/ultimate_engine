"""
VM Prediction Runner (No HKJC Scraping)
========================================
Runs on the Vultr VM. Only calls Gemini AI + Google APIs.
Expects racecard files to already be present (synced from PC).

Usage:
    python3 scripts/vm_predict.py --date 2026-03-29 --venue ST
"""
import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.prediction_engine import PredictionEngine
from services.generate_weather_intel import WeatherAnalyzer


async def run_predictions(date_str: str, venue: str):
    # 1. Weather Intelligence (Google APIs only)
    print(f"\n--- Weather Intelligence for {venue} ---")
    try:
        wie = WeatherAnalyzer()
        await wie.analyze(venue=venue, date_str=date_str)
        print("Weather intel generated.")
    except Exception as e:
        print(f"[WARN] Weather intel failed: {e}")

    # 2. AI Predictions (Gemini only)
    print(f"\n--- AI Predictions for {date_str} ({venue}) ---")
    pe = PredictionEngine()
    for r in range(1, 12):
        try:
            pred = await pe.predict(date_str, venue, r)
            if pred:
                print(f"  R{r}: OK (confidence={pred.get('confidence_score', '?')})")
            else:
                print(f"  R{r}: SKIP (no racecard data)")
        except Exception as e:
            print(f"  R{r}: ERROR - {e}")

    print("\nPrediction run complete.")


def main():
    parser = argparse.ArgumentParser(description="VM Prediction Runner")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--venue", type=str, required=True)
    args = parser.parse_args()

    asyncio.run(run_predictions(args.date, args.venue))


if __name__ == "__main__":
    main()
