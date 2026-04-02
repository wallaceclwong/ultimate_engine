import os
import sys
import json
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from telegram_service import telegram_service

# Configuration
BASE_DIR = Path(__file__).parent.absolute()
FIXTURES_FILE = BASE_DIR / "data" / "fixtures_season.json"
PYTHON_EXEC = "/usr/bin/python3"  # Standard on Vultr Ubuntu

def get_today_fixture():
    """Checks if today is a race day based on the season fixtures."""
    if not FIXTURES_FILE.exists():
        print(f"[ERROR] Fixtures file not found: {FIXTURES_FILE}")
        return None
        
    today_str = datetime.now().strftime("%d/%m/%Y")
    # Handle leading zero if HKJC format is 8/03/2026 instead of 08/03/2026
    today_alt = datetime.now().strftime("%-d/%m/%Y") 
    
    with open(FIXTURES_FILE, "r") as f:
        fixtures = json.load(f)
        for fxt in fixtures:
            if fxt["date"] in [today_str, today_alt]:
                return fxt
    return None

async def run_scrape():
    """Triggers the noon scraping of racecards."""
    print(f"[{datetime.now()}] --- STARTING NOON SCRAPE ---")
    script = BASE_DIR / "scripts" / "smart_racecard_fetcher.py"
    
    # Run the fetcher
    cmd = [PYTHON_EXEC, str(script)]
    process = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    
    if process.returncode == 0:
        await telegram_service.send_message("✅ *Vultr VM*: Noon racecard & odds scraped successfully.")
    else:
        await telegram_service.send_message(f"⚠️ *Vultr VM*: Scrape failed!\n{process.stderr[:100]}")

async def run_predict(venue):
    """Triggers the pre-race predictions and DeepSeek audit."""
    print(f"[{datetime.now()}] --- STARTING PRE-RACE PREDICTIONS ---")
    today_iso = datetime.now().strftime("%Y-%m-%d")
    script = BASE_DIR / "predict_today.py"
    
    # Run predict_today.py
    cmd = [PYTHON_EXEC, str(script), today_iso, venue]
    process = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    
    if process.returncode == 0:
        # The output of predict_today.py contains the DeepSeek reasoning.
        # We'll parse the 'Elite Tips' and notify.
        output = process.stdout
        await telegram_service.send_message(f"🧠 *Ultimate Engine*: Predictions generated for {venue}.\nCheck logs for full strategic brief.")
    else:
        await telegram_service.send_message(f"⚠️ *Vultr VM*: Prediction failed!\n{process.stderr[:100]}")

async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else None
    
    if mode == "--check":
        fxt = get_today_fixture()
        if fxt:
            print(f"RACE DAY: {fxt['venue']} ({fxt['type']})")
        else:
            print("NO RACE TODAY")
            
    elif mode == "--noon":
        fxt = get_today_fixture()
        if fxt:
            await run_scrape()
        else:
            print("Skipping noon scrape: Not a local race day.")
            
    elif mode == "--predict":
        fxt = get_today_fixture()
        if fxt:
            await run_predict(fxt['venue'])
        else:
            print("Skipping predictions: Not a local race day.")

if __name__ == "__main__":
    asyncio.run(main())
