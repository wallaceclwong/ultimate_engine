"""
PC Race Day Orchestrator
========================
Runs on your home PC (residential IP) to handle all HKJC scraping,
then syncs data to Vultr VM for AI prediction generation.

Usage:
    python scripts/pc_race_day.py              # Auto-detect today's meeting
    python scripts/pc_race_day.py --date 2026-03-29 --venue ST
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VM_HOST = "root@100.109.76.69"  # Vultr VM via Tailscale
VM_PATH = "/opt/ultimate_engine"

def load_fixtures(date_str):
    year = datetime.strptime(date_str, "%Y-%m-%d").year
    fixtures_path = PROJECT_ROOT / "data" / f"fixtures_{year}.json"
    if fixtures_path.exists():
        with open(fixtures_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def find_meeting(date_str):
    """Find fixture for a given date."""
    fixtures = load_fixtures(date_str)
    target_dt = datetime.strptime(date_str, "%Y-%m-%d")
    target_fmt = target_dt.strftime("%d/%m/%Y")
    for f in fixtures:
        if f["date"] == target_fmt:
            return f["venue"]
    return None

def find_upcoming_meetings():
    """Find meetings within next 7 days."""
    now = datetime.now().date()
    meetings = []
    for day_offset in range(8):
        d = now + timedelta(days=day_offset)
        d_str = d.strftime("%Y-%m-%d")
        venue = find_meeting(d_str)
        if venue:
            meetings.append({"date": d_str, "venue": venue})
    return meetings

def run_cmd(cmd, timeout=300):
    print(f"  > {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(PROJECT_ROOT))
        if result.returncode != 0:
            print(f"  [WARN] Exit {result.returncode}: {result.stderr[:200]}")
        else:
            out = result.stdout.strip()
            if out:
                print(f"  {out[:200]}")
        return result.returncode == 0
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False

def scrape_racecards(date_str, venue, max_races=11):
    """Step 1: Scrape racecards from HKJC (residential IP)."""
    print(f"\n{'='*60}")
    print(f"STEP 1: Scraping racecards from HKJC ({date_str} {venue})")
    print(f"{'='*60}")
    
    date_fmt = date_str.replace("-", "/")
    py = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
    script = str(PROJECT_ROOT / "services" / "racecard_ingest.py")
    
    for r in range(1, max_races + 1):
        print(f"\n  Race {r}:")
        run_cmd([py, script, "--date", date_fmt, "--venue", venue, "--race", str(r)])

def sync_to_vm(date_str):
    """Step 2: SCP racecard files to VM."""
    print(f"\n{'='*60}")
    print(f"STEP 2: Syncing racecards to VM")
    print(f"{'='*60}")
    
    date_compact = date_str.replace("-", "")
    racecard_files = list((PROJECT_ROOT / "data").glob(f"racecard_{date_compact}_R*.json"))
    
    if not racecard_files:
        print("  [WARN] No racecard files found to sync!")
        return False
    
    for f in racecard_files:
        run_cmd(["scp", "-o", "ConnectTimeout=10", str(f), f"{VM_HOST}:{VM_PATH}/data/{f.name}"])
    
    print(f"  Synced {len(racecard_files)} racecard files to VM")
    return True

def trigger_vm_predictions(date_str, venue):
    """Step 3: Trigger AI predictions on VM (Gemini, no HKJC scraping)."""
    print(f"\n{'='*60}")
    print(f"STEP 3: Triggering AI predictions on VM ({date_str} {venue})")
    print(f"{'='*60}")
    
    cmd = (
        f"cd {VM_PATH} && "
        f"export PYTHONPATH={VM_PATH} && "
        f"set -a && . {VM_PATH}/.env && set +a && "
        f"python3 scripts/vm_predict.py --date {date_str} --venue {venue}"
    )
    
    run_cmd(["ssh", "-o", "ConnectTimeout=10", VM_HOST, cmd], timeout=600)

def start_local_watchdog():
    """Step 4: Start local market watchdog for live odds."""
    print(f"\n{'='*60}")
    print(f"STEP 4: Starting local market watchdog (residential IP)")
    print(f"{'='*60}")
    print("  Watchdog runs via localhost:8000 server startup.")
    print("  Make sure your local server is running:")
    print("  python -m uvicorn dashboard.server:app --host 0.0.0.0 --port 8000")

def main():
    parser = argparse.ArgumentParser(description="PC Race Day Orchestrator")
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--venue", type=str, default=None)
    args = parser.parse_args()
    
    if args.date and args.venue:
        meetings = [{"date": args.date, "venue": args.venue}]
    elif args.date:
        venue = find_meeting(args.date)
        if not venue:
            print(f"No meeting found for {args.date}")
            return
        meetings = [{"date": args.date, "venue": venue}]
    else:
        meetings = find_upcoming_meetings()
        if not meetings:
            print("No upcoming meetings found.")
            return
    
    for m in meetings:
        date_str, venue = m["date"], m["venue"]
        print(f"\n{'#'*60}")
        print(f"# Processing: {date_str} ({venue})")
        print(f"{'#'*60}")
        
        scrape_racecards(date_str, venue)
        if sync_to_vm(date_str):
            trigger_vm_predictions(date_str, venue)
    
    start_local_watchdog()
    print(f"\n{'='*60}")
    print("DONE! Predictions will be generated on VM and synced to Firestore.")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
