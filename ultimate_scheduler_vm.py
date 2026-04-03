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
<<<<<<< HEAD
STATE_FILE = BASE_DIR / "data" / "scheduler_state.json"

def load_scheduler_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"audited_races": []}

def save_scheduler_state(state):
    os.makedirs(STATE_FILE.parent, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_dynamic_schedule():
    """Reads all racecard files for today to build a jump-time map."""
    today_compact = datetime.now().strftime("%Y%m%d")
    schedule = {}
    for r in range(1, 14):
        rc_file = BASE_DIR / "data" / f"racecard_{today_compact}_R{r}.json"
        if rc_file.exists():
            try:
                with open(rc_file, "r") as f:
                    data = json.load(f)
                    jt = data.get("jump_time")
                    if jt:
                        schedule[r] = jt
            except: pass
    return schedule
=======

def get_today_fixture():
>>>>>>> 85f74059cc4211783be2a1b259a9ef24c87ae229
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

<<<<<<< HEAD
async def run_live_war_room(venue):
    """
    Main polling loop for Race Day.
    Checks the 'T-15 minute' window for each race and runs DeepSeek-R1 audits.
    """
    from services.live_audit_service import live_audit_service
    
    print(f"[{datetime.now()}] --- STARTING LIVE WAR ROOM (Venue: {venue}) ---")
    await telegram_service.send_message(f"📡 *Ultimate Engine*: Live War Room active for {venue}.\nWaiting for Smart Money signatures...")

    # Load dynamic schedule and persistence state
    schedule = get_dynamic_schedule()
    state = load_scheduler_state()

    while True:
        now = datetime.now()
        hkt_now = now.strftime("%H:%M") # Assumes VM is in HKT or synced
        
        for r_no, j_time in schedule.items():
            if str(r_no) in state["audited_races"]:
                continue
            
            # Simple HKT countdown (e.g. j_time = "13:00")
            try:
                j_dt = datetime.strptime(j_time.replace(" ",""), "%H:%M")
                now_dt = datetime.strptime(hkt_now, "%H:%M")
                diff_min = (j_dt - now_dt).total_seconds() / 60
                
                # TRIGGER: Window between T-16 and T-14 minutes
                if 14 <= diff_min <= 16:
                    print(f"[EVENT] Audit Window Triggered for R{r_no} (Jump: {j_time})...")
                    # In a full prod version, we'd fetch the specific horse from morning predictions
                    # For Apr 6, we'll auto-check the top 2 EV horses for each race
                    success = await live_audit_service.audit_late_money(venue, r_no)
                    
                    if success:
                        state["audited_races"].append(str(r_no))
                        save_scheduler_state(state)
            except Exception as e:
                print(f"[WARN] Schedule parse error for R{r_no} ({j_time}): {e}")
        
        # Every 60 seconds
        print(f"[{now.strftime('%H:%M:%S')}] Polling market for anomalies...")
        await asyncio.sleep(60)

=======
>>>>>>> 85f74059cc4211783be2a1b259a9ef24c87ae229
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
<<<<<<< HEAD
            
    elif mode == "--live":
        fxt = get_today_fixture()
        if fxt:
            await run_live_war_room(fxt['venue'])
        else:
            print("Skipping Live War Room: Not a local race day.")
=======
>>>>>>> 85f74059cc4211783be2a1b259a9ef24c87ae229

if __name__ == "__main__":
    asyncio.run(main())
