import asyncio
import argparse
import sys
import os
import json
import random
from pathlib import Path
from datetime import datetime
from loguru import logger

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.prediction_engine import PredictionEngine
from services.rl_optimizer import RLOptimizer

async def recalibrate(years: list, sample_rate: float, limit_meetings: int = None):
    """
    Automates the recalibration of AI biases using historical data.
    """
    base_dir = Config.BASE_DIR
    data_dir = base_dir / "data"
    results_dir = data_dir / "results"
    analytical_dir = data_dir / "analytical"
    predictions_dir = data_dir / "predictions"
    
    engine = PredictionEngine()
    optimizer = RLOptimizer()
    
    all_meetings = []
    
    # 1. Collect all meetings from relevant fixture files
    for year in years:
        fixture_file = data_dir / f"fixtures_{year}.json"
        if not fixture_file.exists():
            logger.warning(f"Fixture file missing: {fixture_file}")
            continue
            
        with open(fixture_file, "r", encoding="utf-8") as f:
            fixtures = json.load(f)
            # Normalize dates and add to list
            for m in fixtures:
                try:
                    dt = datetime.strptime(m["date"], "%d/%m/%Y")
                    m["date_str"] = dt.strftime("%Y-%m-%d")
                    all_meetings.append(m)
                except Exception as e:
                    logger.error(f"Error parsing date in {fixture_file}: {m.get('date')} - {e}")

    logger.info(f"Found {len(all_meetings)} total meetings across years {years}")
    
    # 2. Sample meetings
    if sample_rate < 1.0:
        sample_size = int(len(all_meetings) * sample_rate)
        sampled_meetings = random.sample(all_meetings, sample_size)
        logger.info(f"Sampled {sample_size} meetings (rate={sample_rate})")
    else:
        sampled_meetings = all_meetings
        
    if limit_meetings:
        sampled_meetings = sampled_meetings[:limit_meetings]
        logger.info(f"Limited to {len(sampled_meetings)} meetings")

    # 3. Ensure predictions exist for sampled meetings
    final_prediction_files = []
    
    for meeting in sampled_meetings:
        date_str = meeting["date_str"]
        venue = meeting["venue"]
        
        # Find races for this meeting
        race_files = list(results_dir.glob(f"results_{date_str}_{venue}_R*.json"))
        if not race_files:
            logger.debug(f"No results found for {date_str} {venue}, skipping.")
            continue
            
        race_numbers = sorted([int(f.stem.split("_R")[-1]) for f in race_files])
        
        for race_no in race_numbers:
            race_id = f"{date_str}_{venue}_R{race_no}"
            pred_file = predictions_dir / f"prediction_{race_id}.json"
            analytical_file = analytical_dir / f"analytical_{race_id}.json"
            
            if not analytical_file.exists():
                logger.debug(f"Missing analytical data for {race_id}, skipping.")
                continue
                
            if not pred_file.exists():
                logger.info(f"Generating missing prediction for {race_id}...")
                try:
                    await engine.generate_prediction(date_str, venue, race_no)
                except Exception as e:
                    logger.error(f"Failed to generate prediction for {race_id}: {e}")
                    continue
            
            if pred_file.exists():
                final_prediction_files.append(pred_file)

    logger.info(f"Collected {len(final_prediction_files)} predictions for recalibration.")

    # 4. Run Optimization
    if final_prediction_files:
        logger.info("Starting bias optimization...")
        optimizer.optimize_from_subset(final_prediction_files)
        logger.info("Recalibration complete.")
    else:
        logger.warning("No predictions available for recalibration.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recalibrate AI Biases from Historical Data")
    parser.add_argument("--years", type=str, default="2024,2025", help="Comma-separated years (e.g. 2018,2019,2020)")
    parser.add_argument("--sample", type=float, default=0.1, help="Sample rate (0.0 to 1.0)")
    parser.add_argument("--limit", type=int, default=None, help="Limit total meetings")
    
    args = parser.parse_args()
    
    year_list = [y.strip() for y in args.years.split(",")]
    
    asyncio.run(recalibrate(year_list, args.sample, args.limit))
