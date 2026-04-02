import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import json
from datetime import datetime
from services.browser_manager import BrowserManager

class OddsIngest:
    def __init__(self, headless=True):
        self.headless = headless
        self.browser_mgr = BrowserManager(headless=headless)

    async def fetch_odds(self, date_str: str, race_no: int = 1, venue: str = "ST", close_browser: bool = True):
        """
        Fetches real-time Win & Place odds for a specific race.
        """
        url = f"https://bet.hkjc.com/en/racing/wp/{date_str}/{venue}/{race_no}"
        
        page = await self.browser_mgr.get_page()

        print(f"Navigating to {url}...")
        try:
            await page.goto(url, wait_until="load", timeout=30000)
            
            # Wait for content to load 
            await page.wait_for_selector(f'#wpleg_WIN_{race_no}_1', timeout=30000)
            
            print(f"Extracting odds for Race {race_no}...")
            
            win_odds = {}
            place_odds = {}

            # Max 14 horses usually in HKJC
            for horse_num in range(1, 15): 
                try:
                    # Win Odds
                    win_elem = await page.query_selector(f'#odds_WIN_{race_no}_{horse_num} a')
                    if win_elem:
                        val = (await win_elem.inner_text()).strip()
                        if val and val != '-' and val != '':
                            win_odds[str(horse_num)] = float(val)

                    # Place Odds
                    place_elem = await page.query_selector(f'#odds_PLA_{race_no}_{horse_num} a')
                    if place_elem:
                        val = (await place_elem.inner_text()).strip()
                        if val and val != '-' and val != '':
                            place_odds[str(horse_num)] = float(val)
                except Exception as e:
                    continue

            await page.close()
            if close_browser:
                await self.browser_mgr.stop()
            return {
                "venue": venue,
                "race_no": race_no,
                "win_odds": win_odds,
                "place_odds": place_odds,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            print(f"Error fetching odds: {e}")
            await self.browser_mgr.stop()
            return None

    async def capture_snapshot(self, date_str: str, race_no: int, venue: str = "ST") -> bool:
        """
        Fetches odds and saves a snapshot to data/odds/
        """
        data = await self.fetch_odds(date_str=date_str, race_no=race_no, venue=venue)
        if data:
            # Ensure directory exists
            odds_dir = Path(root_dir) / "data" / "odds"
            odds_dir.mkdir(parents=True, exist_ok=True)
            
            # Normalize date for filename
            date_path = date_str.replace("-", "").replace("/", "")
            timestamp = int(datetime.now().timestamp())
            filename = odds_dir / f"snapshot_{date_path}_R{race_no}_{timestamp}.json"
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                
            print(f"Captured snapshot for Race {race_no} to {filename}")
            return True
        return False

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingest HKJC Odds")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--venue", type=str, default="HV")
    parser.add_argument("--race", type=int, default=1)
    args = parser.parse_args()

    # Normalize date for filename
    date_path = args.date.replace("-", "").replace("/", "")

    ingest = OddsIngest()
    data = await ingest.fetch_odds(date_str=args.date, race_no=args.race, venue=args.venue)
    if data:
        # Ensure directory exists
        odds_dir = Path(root_dir) / "data" / "odds"
        odds_dir.mkdir(parents=True, exist_ok=True)
        
        # Save snapshot
        timestamp = int(datetime.now().timestamp())
        filename = odds_dir / f"snapshot_{date_path}_R{args.race}_{timestamp}.json"
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        print(f"Success: Odds for Race {args.race} saved to {filename}")

if __name__ == "__main__":
    asyncio.run(main())
