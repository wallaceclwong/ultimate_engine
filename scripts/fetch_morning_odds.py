import sys
import subprocess
from pathlib import Path
import time
import argparse

BASE_DIR = Path(__file__).resolve().parent.parent

def fetch_all_odds(date_str: str, venue: str, max_races: int = 11):
    print(f"============================================================")
    print(f"FETCHING MORNING ODDS for {date_str} ({venue})")
    print(f"============================================================")
    
    odds_script = BASE_DIR / "services" / "odds_ingest.py"
    py = sys.executable

    for r in range(1, max_races + 1):
        print(f"  Race {r}...", end=" ", flush=True)
        cmd = [py, str(odds_script), "--date", date_str, "--venue", venue, "--race", str(r)]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
        
        if result.returncode == 0:
            print("[OK]")
        else:
            print(f"[FAIL] {result.stderr.strip()}")
            
        time.sleep(1) # Polite delay
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--venue", required=True)
    parser.add_argument("--races", type=int, default=11)
    args = parser.parse_args()
    
    fetch_all_odds(args.date, args.venue, args.races)
