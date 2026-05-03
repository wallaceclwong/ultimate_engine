import asyncio
import sys
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.odds_ingest import OddsIngest

async def main():
    date_str = "2026-05-03"
    venue = "ST"
    
    ingest = OddsIngest(headless=True)
    
    print(f"Scraping odds for all races on {date_str} at {venue}...")
    
    for race_no in range(1, 12):
        print(f"\n--- Race {race_no} ---")
        success = await ingest.capture_snapshot(date_str=date_str, race_no=race_no, venue=venue)
        if success:
            print(f"✓ Race {race_no} odds captured")
        else:
            print(f"✗ Race {race_no} failed")
    
    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(main())
