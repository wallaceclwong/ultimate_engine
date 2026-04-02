import asyncio
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config
from services.prediction_engine import PredictionEngine
from services.betting_evaluator import BettingEvaluator

class BacktestEngine:
    def __init__(self, fixtures_path: str = "data/fixtures_2025.json"):
        self.prediction_engine = PredictionEngine()
        self.evaluator = BettingEvaluator()
        self.fixtures_path = Path(fixtures_path)
        self.results_dir = Path("data/results")
        self.analytical_dir = Path("data/analytical")


    def load_fixtures(self) -> List[Dict[str, Any]]:
        with open(self.fixtures_path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def run_backtest(self, start_date: str = None, end_date: str = None, limit: int = None):
        """
        Runs a backtest simulations for the specified date range.
        If no range is provided, it iterates through all 2025 fixtures.
        """
        fixtures = self.load_fixtures()
        
        # Filter fixtures by date if provided
        if start_date or end_date:
            filtered = []
            start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
            
            for f in fixtures:
                # Parse fixture date (D/MM/YYYY)
                f_dt = datetime.strptime(f["date"], "%d/%m/%Y")
                
                # Check bounds
                if start_dt and f_dt < start_dt:
                    continue
                if end_dt and f_dt > end_dt:
                    continue
                
                # Normalize the fixture date for the rest of the script
                f["date"] = f_dt.strftime("%Y-%m-%d")
                filtered.append(f)
            fixtures = filtered
        else:
            # Even if no filters, normalize all dates
            for f in fixtures:
                f_dt = datetime.strptime(f["date"], "%d/%m/%Y")
                f["date"] = f_dt.strftime("%Y-%m-%d")
        
        if limit:
            fixtures = fixtures[:limit]

        print(f"\nStarting Backtest Simulation on {len(fixtures)} meetings...")
        
        for meeting in fixtures:
            date_str = meeting["date"]
            venue = meeting["venue"]
            print(f"\n>>> Simulating Meeting: {date_str} ({venue})")
            
            # Identify available races for this meeting in the local cache
            # We look for results_YYYY-MM-DD_VENUE_R*.json
            race_files = list(self.results_dir.glob(f"results_{date_str}_{venue}_R*.json"))
            if not race_files:
                print(f"Skipping: No result data found for {date_str}")
                continue
                
            # Extract race numbers and sort
            race_numbers = sorted([int(f.stem.split("_R")[-1]) for f in race_files])
            
            for race_no in race_numbers:
                race_id = f"{date_str}_{venue}_R{race_no}"
                
                # Check if analytical data exists (required for deep prediction)
                analytical_file = self.analytical_dir / f"analytical_{race_id}.json"
                if not analytical_file.exists():
                    print(f"  R{race_no}: Skipping (Missing analytical data)")
                    continue

                # Check if prediction already exists (to avoid duplicate costs/time during dev)
                prediction_file = Path(f"data/predictions/prediction_{race_id}.json")
                if prediction_file.exists():
                    print(f"  R{race_no}: OK (Prediction already exists)")
                else:
                    print(f"  R{race_no}: Generating Prediction...")
                    await self.prediction_engine.generate_prediction(date_str, venue, race_no)
                    # Add a 3-second buffer to respect Vertex AI quotas during heavy backtesting
                    await asyncio.sleep(3)
            
            # Evaluate the meeting performance
            print(f"\n--- Performance Evaluation for {date_str} ---")
            self.evaluator.evaluate_day(date_str, venue)

        print("\nBacktest Simulation Complete.")

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="HKJC Backtest Simulation Engine")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, help="Limit number of meetings to simulate")
    parser.add_argument("--fixtures", type=str, default="data/fixtures_2025.json", help="Path to fixtures file")
    args = parser.parse_args()

    engine = BacktestEngine(fixtures_path=args.fixtures)
    await engine.run_backtest(start_date=args.start, end_date=args.end, limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
