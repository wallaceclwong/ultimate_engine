import os
import sys
from pathlib import Path
import re

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.betting_evaluator import BettingEvaluator

def sweep_all():
    evaluator = BettingEvaluator()
    predictions_dir = Path("data/predictions")
    
    if not predictions_dir.exists():
        print("No predictions found to evaluate.")
        return

    # Extract unique dates and venues from prediction files
    # Format: prediction_2025-03-30_ST_R1.json
    pattern = re.compile(r"prediction_(\d{4}-\d{2}-\d{2})_([A-Z]{2})_R\d+\.json")
    meetings = set()
    
    for f in predictions_dir.glob("prediction_*.json"):
        match = pattern.match(f.name)
        if match:
            meetings.add((match.group(1), match.group(2)))

    sorted_meetings = sorted(list(meetings))
    print(f"Found {len(sorted_meetings)} unique meetings with predictions to evaluate...")

    for date_str, venue in sorted_meetings:
        print(f"\nProcessing Meeting: {date_str} ({venue})")
        evaluator.evaluate_day(date_str, venue)

    print("\nROI Sweep Complete. All results mirrored to BigQuery.")

if __name__ == "__main__":
    sweep_all()
