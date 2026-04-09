import os
import sys
import json
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
import pandas as pd
from telegram_service import telegram_service

# Configuration
BASE_DIR = Path(__file__).parent.absolute()
FIXTURES_FILE = BASE_DIR / "data" / "fixtures_season.json"
PYTHON_EXEC = sys.executable  # Cross-platform (Windows/Linux)
STATE_FILE = BASE_DIR / "data" / "scheduler_state.json"

def load_scheduler_state():
    today = datetime.now().strftime("%Y-%m-%d")
    default_state = {"audited_races": [], "learned_today": False, "last_reset_date": today}
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            try:
                state = json.load(f)
                # Reset if it's a new day
                if state.get("last_reset_date") != today:
                    print(f"[SYSTEM] New day detected ({today}): Resetting scheduler state.")
                    return default_state
                return state
            except: pass
    return default_state

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

def get_today_fixture():
    """Checks if today is a race day based on the season fixtures."""
    if not FIXTURES_FILE.exists():
        print(f"[ERROR] Fixtures file not found: {FIXTURES_FILE}")
        return None
        
    now = datetime.now()
    # Format options to match fixtures like "8/04/2026" or "08/04/2026"
    d, m, y = now.day, now.month, now.year
    possible_dates = [
        f"{d}/{m:02d}/{y}",   # 8/04/2026
        f"{d:02d}/{m:02d}/{y}", # 08/04/2026
        f"{d}/{m}/{y}",       # 8/4/2026
        f"{d:02d}/{m}/{y}"    # 08/4/2026
    ]
    
    with open(FIXTURES_FILE, "r") as f:
        fixtures = json.load(f)
        for fxt in fixtures:
            if fxt["date"] in possible_dates:
                print(f"[DEBUG] Fixture found: {fxt['venue']} on {fxt['date']}")
                return fxt
    print(f"[DEBUG] No fixture match for possible dates: {possible_dates}")
    return None

async def run_scrape():
    """Triggers the noon scraping of racecards."""
    print(f"[{datetime.now()}] --- STARTING NOON SCRAPE ---")
    script = BASE_DIR / "scripts" / "smart_racecard_fetcher.py"
    
    # Run the fetcher
    cmd = [PYTHON_EXEC, str(script)]
    process = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    
    if process.returncode == 0:
        await telegram_service.send_message("✅ *Lunar Heartbeat*: Noon racecard & odds scraped successfully.")
    else:
        await telegram_service.send_message(f"⚠️ *Lunar Alert*: Scrape failed!\n{process.stderr[:100]}")

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
        await telegram_service.send_message(f"🧠 *Lunar Intelligence*: Predictions generated for {venue}.\nCheck logs for full strategic brief.")
    else:
        await telegram_service.send_message(f"⚠️ *Vultr VM*: Prediction failed!\n{process.stderr[:100]}")

async def run_learn(venue):
    """Triggers the post-race ingestion and learning scripts."""
    print(f"[{datetime.now()}] --- STARTING POST-RACE LEARNING ---")
    today_iso = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Fetch official results
    script_results = BASE_DIR / "scripts" / "batch_results.py"
    print(f"[LEARN] Step 1: Fetching results for {today_iso} {venue}...")
    cmd1 = [PYTHON_EXEC, str(script_results), today_iso, venue]
    process1 = subprocess.run(cmd1, capture_output=True, text=True, cwd=str(BASE_DIR))
    
    if process1.returncode != 0:
        await telegram_service.send_message(f"⚠️ *Lunar Alert*: Results ingestion failed!\n{process1.stderr[:100]}")
        return False

    # 2. Enrich Pedigree Data
    print(f"[LEARN] Step 2: Enriching pedigree intelligence...")
    script_pedigree = BASE_DIR / "scripts" / "scrape_pedigree.py"
    cmd_ped = [PYTHON_EXEC, str(script_pedigree), "--all"]
    # Run in background or wait? Since it's nightly, we'll wait 
    process_ped = subprocess.run(cmd_ped, capture_output=True, text=True, cwd=str(BASE_DIR))
    if process_ped.returncode == 0:
        print("[LEARN] Pedigree cache updated.")
    else:
        print(f"[ERROR] Pedigree Enrichment failed: {process_ped.stderr}")

    # 3. Memory Sync (MemPalace Mining)
    from services.memory_service import memory_service
    print(f"[LEARN] Step 3: Mining new intelligence into Palace...")
    try:
        # We index the entire data root to capture results, predictions, and processed tables
        memory_service.mine(str(BASE_DIR / "data"))
        await telegram_service.send_message("🧠 *Lunar Memory*: Today's results, predictions, and features successfully mined into Palace.")
    except Exception as e:
        print(f"[MEMORY WARN] Mining failed: {e}")

    # 4. Matrix Update (Training Data Append)
    print(f"[LEARN] Step 4: Updating Master Matrix...")
    script_learn = BASE_DIR / "scripts" / "learn_today.py"
    cmd2 = [PYTHON_EXEC, str(script_learn), today_iso, venue]
    process2 = subprocess.run(cmd2, capture_output=True, text=True, cwd=str(BASE_DIR))

    if process2.returncode == 0:
        print(f"[LEARN] SUCCESS: Matrix updated.")
        await telegram_service.send_message(f"📚 *Lunar Learning*: Today's results ingested and matrix updated for {venue}. Self-learning cycle complete.")
        return True
    else:
        await telegram_service.send_message(f"⚠️ *Lunar Alert*: Learning logic failed!\n{process2.stderr[:100]}")
        return False

async def run_live_war_room(venue):
    """
    Main polling loop for Race Day.
    Checks the 'T-15 minute' window for each race and runs DeepSeek-R1 audits.
    """
    from services.live_audit_service import live_audit_service
    from services.odds_ingest import OddsIngest
    
    ingest = OddsIngest(headless=True)
    
    print(f"[{datetime.now()}] --- STARTING LIVE WAR ROOM (Venue: {venue}) ---")
    await telegram_service.send_message(f"📡 *Lunar War Room*: Active for {venue}.\nWaiting for Smart Money signatures...")

    # Load dynamic schedule and persistence state
    schedule = get_dynamic_schedule()
    state = load_scheduler_state()

    while True:
        now = datetime.now()
        today_iso = now.strftime("%Y-%m-%d")
        hkt_now = now.strftime("%H:%M") # Assumes VM is in HKT or synced
        
        for r_no, j_time in schedule.items():
            if str(r_no) in state["audited_races"]:
                continue
            
            # Simple HKT countdown (e.g. j_time = "13:00")
            try:
                j_dt = datetime.strptime(j_time.strip().replace(" ",""), "%H:%M")
                now_dt = datetime.strptime(hkt_now, "%H:%M")
                diff_min = (j_dt - now_dt).total_seconds() / 60
                
                # 0. LIVE ODDS INGESTION (Every 3 mins if within T-25)
                # We use a state check to prevent hammering the browser
                if 0 <= diff_min <= 25:
                    last_scrape = state.get(f"last_scrape_R{r_no}", 0)
                    if (now.timestamp() - last_scrape) > 180: # 3 minutes
                        print(f"[INGEST] Refreshing live odds for R{r_no}...")
                        await ingest.capture_snapshot(today_iso, int(r_no), venue)
                        state[f"last_scrape_R{r_no}"] = now.timestamp()
                        save_scheduler_state(state)

                # TRIGGER: Window between T-16 and T-14 minutes
                if 14 <= diff_min <= 16:
                    print(f"[EVENT] Audit Window Triggered for R{r_no} (Jump: {j_time})...")
                    try:
                        # 1. Load the horse features to find high-EV candidates
                        feat_file = BASE_DIR / "data" / "processed" / f"features_{today_iso}_{venue}_R{r_no}.parquet"
                        
                        if feat_file.exists():
                            df = pd.read_parquet(feat_file)
                            # Audit top 2 by EV
                            candidates = df.sort_values("ev", ascending=False).head(2)
                            
                            audit_results = []
                            for _, horse in candidates.iterrows():
                                h_no = str(horse["horse_no"])
                                print(f"[AUDIT] Checking Horse #{h_no}...")
                                # Trigger live audit via service
                                res = await live_audit_service.audit_late_money(f"R{r_no}", h_no, today_iso, venue, int(r_no))
                                if res:
                                    audit_results.append(res)
                            
                            if not audit_results:
                                await telegram_service.send_message(f"ℹ️ *Lunar Heartbeat*: Race {r_no} audited. No high-conviction Smart Money detected (Relief Threshold: 7%).")
                        else:
                            print(f"[WARN] No feature file found for R{r_no}: {feat_file}")
                    except Exception as e:
                        print(f"[ERROR] Live audit failed for R{r_no}: {e}")
                    
                    state["audited_races"].append(str(r_no))
                    save_scheduler_state(state)
            except Exception as e:
                print(f"[WARN] Schedule parse error for R{r_no} ({j_time}): {e}")
        
        # 2. Check for Post-Race Learning (23:15 HKT)
        if now.hour == 23 and now.minute >= 15 and not state.get("learned_today"):
            success = await run_learn(venue)
            if success:
                state["learned_today"] = True
                save_scheduler_state(state)
        
        # Every 60 seconds
        print(f"[{now.strftime('%H:%M:%S')}] Polling market for anomalies...")
        await asyncio.sleep(60)

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
            
    elif mode == "--live":
        fxt = get_today_fixture()
        if fxt:
            await run_live_war_room(fxt['venue'])
        else:
            print("Skipping Live War Room: Not a local race day.")
            
    elif mode == "--learn":
        fxt = get_today_fixture()
        if fxt:
            await run_learn(fxt['venue'])
        else:
            # Fallback for non-race days if forced
            await run_learn("ST")

if __name__ == "__main__":
    asyncio.run(main())
