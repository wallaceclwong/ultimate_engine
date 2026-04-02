"""
Smart Racecard Fetcher
======================
Checks for newly published racecards and fetches them immediately.
HKJC publishes racecards right after each meeting ends.

Usage:
    python scripts/smart_racecard_fetcher.py              # Check all upcoming meetings
    python scripts/smart_racecard_fetcher.py --date 2026-04-01 --venue ST
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

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

def get_upcoming_meetings(days_ahead=14):
    """Get all meetings in next 14 days."""
    now = datetime.now().date()
    meetings = []
    for day_offset in range(days_ahead + 1):
        d = now + timedelta(days=day_offset)
        d_str = d.strftime("%Y-%m-%d")
        venue = find_meeting(d_str)
        if venue:
            meetings.append({"date": d_str, "venue": venue, "day_of_week": d.strftime("%A")})
    return meetings

def test_racecard_availability(date_str, venue):
    """Test if racecard is available by checking if file exists or trying to fetch."""
    print(f"Testing racecard availability for {date_str} {venue}...")
    
    # First check if file already exists
    date_compact = date_str.replace("-", "")
    racecard_file = PROJECT_ROOT / "data" / f"racecard_{date_compact}_R1.json"
    if racecard_file.exists():
        print(f"  [OK] Racecard already exists!")
        return True
    
    # If not exists, try to fetch it
    print(f"  File not found, attempting to fetch...")
    date_fmt = date_str.replace("-", "/")
    # Determine python executable based on OS
    if sys.platform == 'win32':
        py = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
    else:
        # Check for linux venv or system python
        venv_py = PROJECT_ROOT / ".venv" / "bin" / "python"
        py = str(venv_py) if venv_py.exists() else "python3"
        
    script = str(PROJECT_ROOT / "services" / "racecard_ingest.py")
    
    cmd = [py, script, "--date", date_fmt, "--venue", venue, "--race", "1"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(PROJECT_ROOT))
    
    if result.returncode == 0:
        # Check if file was created
        if racecard_file.exists():
            print(f"  [OK] Racecard fetched successfully!")
            return True
        else:
            print(f"  [FAIL] No racecard file created")
            return False
    else:
        print(f"  [ERROR] {result.stderr[:100]}")
        return False

def fetch_all_races(date_str, venue, max_races=11):
    """Fetch all races for a meeting."""
    print(f"\nChecking all races for {date_str} {venue}")
    
    date_fmt = date_str.replace("-", "/")
    # Determine python executable based on OS
    if sys.platform == 'win32':
        py = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
    else:
        # Check for linux venv or system python
        venv_py = PROJECT_ROOT / ".venv" / "bin" / "python"
        py = str(venv_py) if venv_py.exists() else "python3"
        
    script = str(PROJECT_ROOT / "services" / "racecard_ingest.py")
    
    success_count = 0
    existing_count = 0
    
    for r in range(1, max_races + 1):
        date_compact = date_str.replace("-", "")
        racecard_file = PROJECT_ROOT / "data" / f"racecard_{date_compact}_R{r}.json"
        
        if racecard_file.exists():
            existing_count += 1
            print(f"  Race {r}... [EXISTS]")
        else:
            print(f"  Race {r}...", end=" ")
            cmd = [py, script, "--date", date_fmt, "--venue", venue, "--race", str(r)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(PROJECT_ROOT))
            
            if result.returncode == 0:
                if racecard_file.exists():
                    success_count += 1
                    print("[OK]")
                else:
                    print("[FAIL] (no file)")
            else:
                print("[FAIL]")
    
    total_count = existing_count + success_count
    print(f"  Total races available: {total_count}/{max_races} ({existing_count} existing, {success_count} newly fetched)")
    return total_count > 0

def main():
    parser = argparse.ArgumentParser(description="Smart Racecard Fetcher")
    parser.add_argument("--date", type=str, default=None, help="Specific date to check")
    parser.add_argument("--venue", type=str, default=None, help="Specific venue to check")
    parser.add_argument("--days", type=int, default=14, help="Days ahead to check")
    args = parser.parse_args()
    
    print("="*60)
    print("SMART RACECARD FETCHER")
    print("="*60)
    
    if args.date and args.venue:
        meetings = [{"date": args.date, "venue": args.venue, "day_of_week": "Custom"}]
    else:
        meetings = get_upcoming_meetings(args.days)
    
    if not meetings:
        print("No upcoming meetings found.")
        return
    
    print(f"\nChecking {len(meetings)} upcoming meetings...")
    
    for m in meetings:
        date_str, venue, day = m["date"], m["venue"], m["day_of_week"]
        print(f"\n{'-'*40}")
        print(f"{day} {date_str} ({venue})")
        print(f"{'-'*40}")
        
        # Test if racecard is available
        if test_racecard_availability(date_str, venue):
            # If available, fetch all races
            fetch_all_races(date_str, venue)
        else:
            print("  Racecard not yet available")
    
    print(f"\n{'='*60}")
    print("DONE! Check data/racecard_*.json for fetched racecards.")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
