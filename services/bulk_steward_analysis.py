import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.steward_analyser import StewardAnalyser

async def run_bulk_analysis(limit=None):
    analyser = StewardAnalyser()
    results_dir = Path("data/results")
    
    # Get all unique meetings from results
    # Format: results_YYYY-MM-DD_VENUE_RX.json
    result_files = list(results_dir.glob("results_*.json"))
    
    meetings = set()
    for f in result_files:
        parts = f.name.split("_")
        if len(parts) >= 3:
            date_str = parts[1]
            venue = parts[2]
            meetings.add((date_str, venue))
    
    sorted_meetings = sorted(list(meetings), reverse=True) # Start from most recent
    
    if limit:
        sorted_meetings = sorted_meetings[:limit]
        
    print(f"[BULK] Starting analysis for {len(sorted_meetings)} meetings...")
    
    for i, (date_str, venue) in enumerate(sorted_meetings):
        print(f"[{i+1}/{len(sorted_meetings)}] Analysing {date_str} {venue}...")
        try:
            await analyser.analyse_meeting_incidents(date_str, venue)
            # Small sleep to avoid hitting rate limits too hard
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Error analysing {date_str} {venue}: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Bulk Steward Analysis")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of meetings to analyse")
    args = parser.parse_args()
    
    asyncio.run(run_bulk_analysis(limit=args.limit))
