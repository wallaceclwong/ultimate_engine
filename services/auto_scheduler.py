import time
import subprocess
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.firestore_service import FirestoreService

def run_task(command):
    """Runs a subprocess and logs output."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Executing: {' '.join(command)}")
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(f"  > {line.strip()}")
        process.wait()
        return process.returncode == 0
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False

def check_for_upcoming_meetings():
    """Checks fixtures and runs daily_runner for upcoming 3 days."""
    today = datetime.now()
    
    # Check fixtures_2026.json (assuming current year)
    fixtures_path = Path("data/fixtures_2026.json")
    if not fixtures_path.exists():
        print(f"Fixtures file {fixtures_path} not found. Skipping auto-fetch.")
        return

    import json
    with open(fixtures_path, "r", encoding="utf-8") as f:
        fixtures = json.load(f)

    for i in range(0, 4):  # Check today + next 3 days
        target_date = today + timedelta(days=i)
        target_str = target_date.strftime("%d/%m/%Y")
        iso_str = target_date.strftime("%Y-%m-%d")
        
        meeting = next((f for f in fixtures if f["date"] == target_str), None)
        if meeting:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Upcoming meeting detected: {iso_str}")
            
            # Check if racecards already exist
            date_compact = iso_str.replace("-", "")
            if not list(Path("data").glob(f"racecard_{date_compact}_R1.json")):
                print(f"  [AUTO] Triggering racecard fetch for {iso_str}...")
                run_task([sys.executable, "services/daily_runner.py", "--date", iso_str])
            else:
                print(f"  [SKIP] Racecards for {iso_str} already exist.")

def main_loop():
    print("="*60)
    print("HKJC AUTO-SCHEDULER STARTING")
    print("="*60)
    
    while True:
        try:
            # 1. Update fixtures (optional: could run test_schedule.py here)
            # 2. Check and fetch upcoming racecards
            check_for_upcoming_meetings()
            
            # 3. Wait for 6 hours before next full check
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Sleeping for 6 hours...")
            time.sleep(6 * 3600)
            
        except KeyboardInterrupt:
            print("\nScheduler stopped by user.")
            break
        except Exception as e:
            print(f"\n[CRITICAL ERROR] Scheduler loop encountered exception: {e}")
            time.sleep(300) # Wait 5 minutes before retry

if __name__ == "__main__":
    main_loop()
