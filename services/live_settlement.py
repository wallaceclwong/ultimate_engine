import asyncio
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config
from services.results_ingest import ResultsIngest
from services.firestore_service import FirestoreService

class LiveSettlement:
    def __init__(self, date_str: str = None, venue: str = None):
        self.date_str = date_str or datetime.now().strftime("%Y-%m-%d")
        self.venue = venue
        self.ingest = ResultsIngest(headless=True)
        self.firestore = FirestoreService()
        self.settled_races = set()
        
    async def run_loop(self, interval=300):
        """
        Polls for results every 'interval' seconds.
        """
        logger.info(f"🏁 Starting Live Settlement for {self.date_str} {self.venue if self.venue else '(auto)'}...")
        
        while True:
            try:
                # 1. Detect Meeting if not provided
                if not self.venue:
                    self.venue = self._auto_detect_venue()
                
                if not self.venue:
                    logger.warning("No meeting detected for today. Sleeping...")
                    await asyncio.sleep(3600)
                    continue

                # 2. Iterate through potential races (1-12)
                for r in range(1, 13):
                    race_id = f"{self.date_str}_{self.venue}_R{r}"
                    if race_id in self.settled_races:
                        continue
                    
                    # 3. Check if result exists in Cloud (save bandwidth)
                    if self.firestore.get_document(Config.COL_RESULTS, race_id):
                        logger.info(f"✅ Race {r} already settled in Cloud.")
                        self.settled_races.add(race_id)
                        continue
                    
                    # 4. Try to fetch live result
                    logger.info(f"🔍 Checking results for Race {r}...")
                    data = await self.ingest.fetch_results(self.date_str, venue=self.venue, race_no=r)
                    
                    if data and data.get("results") and len(data["results"]) > 0:
                        logger.success(f"🏆 Results FOUND for Race {r}! Syncing to Cloud...")
                        
                        # Save local copy
                        os.makedirs("data/results", exist_ok=True)
                        with open(f"data/results/results_{race_id}.json", "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        
                        # Sync to Firestore
                        self.firestore.upsert(Config.COL_RESULTS, race_id, data)
                        self.settled_races.add(race_id)
                        
                        # Optional: Trigger ROI update notification
                        logger.info(f"Race {r} settlement complete.")
                    else:
                        # If Race N has no results, Race N+1 definitely won't
                        logger.info(f"⏳ Race {r} results not yet available.")
                        break
                
                # Sleep until next poll
                logger.info(f"Sleeping for {interval}s...")
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in LiveSettlement loop: {e}")
                await asyncio.sleep(60)

    def _auto_detect_venue(self):
        """Finds today's venue from fixtures."""
        fixtures_path = Path(Config.BASE_DIR) / "data" / "fixtures_2026.json"
        if not fixtures_path.exists():
            return None
            
        today_hkt = (datetime.now()).strftime("%d/%m/%Y")
        try:
            with open(fixtures_path, "r", encoding="utf-8") as f:
                fixtures = json.load(f)
                for fxt in fixtures:
                    if fxt["date"] == today_hkt:
                        return fxt["venue"]
        except:
            pass
        return None

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HKJC Live Settlement Service")
    parser.add_argument("--date", type=str, default=None, help="Date in YYYY-MM-DD")
    parser.add_argument("--venue", type=str, default=None, help="Venue (ST or HV)")
    parser.add_argument("--interval", type=int, default=300, help="Polling interval in seconds")
    args = parser.parse_args()

    settlement = LiveSettlement(date_str=args.date, venue=args.venue)
    asyncio.run(settlement.run_loop(interval=args.interval))
