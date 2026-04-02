import asyncio
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from services.results_ingest import ResultsIngest
from services.browser_manager import BrowserManager

async def auto_result_ingest():
    """
    Automatically detects the most recent racing day and ingests all results.
    """
    print("🚀 Starting Automated Result Ingestion...")
    
    # 1. Determine target date (Yesterday or Today)
    # Most races end by 23:00 HKT, so we check if results are available for today
    today = datetime.now()
    target_date = today.strftime("%Y-%m-%d")
    
    ingest = ResultsIngest(headless=True)
    browser_mgr = BrowserManager(headless=True)
    page = await browser_mgr.get_page()
    
    venues = ["ST", "HV"]
    success_count = 0
    
    # Standard racing days are Wed (2), Sat (5), Sun (6)
    # We check today first, then fallback to yesterday
    dates_to_check = [today, today - timedelta(days=1)]
    
    for dt in dates_to_check:
        date_str = dt.strftime("%Y-%m-%d")
        print(f"🧐 Checking for results on {date_str}...")
        
        for venue in venues:
            # We try race 1 first to see if the meeting exists
            data = await ingest.fetch_results(date_str, venue=venue, race_no=1, page=page)
            
            if data and data['results']:
                print(f"✅ Meeting found for {date_str} at {venue}. Fetching all races...")
                
                # Save race 1
                os.makedirs("data/results", exist_ok=True)
                with open(f"data/results/results_{data['race_id']}.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                success_count += 1
                
                # Fetch remaining races (up to 12)
                for r in range(2, 13):
                    race_data = await ingest.fetch_results(date_str, venue=venue, race_no=r, page=page)
                    if not race_data or not race_data['results']:
                        print(f"🏁 End of meeting at Race {r-1}")
                        break
                    
                    filename = f"data/results/results_{race_data['race_id']}.json"
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(race_data, f, indent=2)
                    print(f"✅ Saved Race {r}")
                    success_count += 1
                
                # If we found a meeting, we stop (don't check older dates unless multiple meetings per day)
                await browser_mgr.stop()
                print(f"🎉 Successfully ingested {success_count} races.")
                return True
                
    print("❌ No recent race results found.")
    await browser_mgr.stop()
    return False

if __name__ == "__main__":
    asyncio.run(auto_result_ingest())
