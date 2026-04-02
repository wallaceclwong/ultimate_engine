import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Add project root for direct imports in settlement step
sys.path.insert(0, str(Path(__file__).parent.parent))

def load_fixtures(date_str=None):
    """
    Loads fixture data. Automatically selects the correct year-based fixture file.
    """
    base_dir = Path(__file__).resolve().parent.parent / "data"
    year = None
    if date_str:
        try:
            year = datetime.strptime(date_str, "%Y-%m-%d").year
        except:
            pass
    if year:
        year_fixture = base_dir / f"fixtures_{year}.json"
        if year_fixture.exists():
            with open(year_fixture, "r", encoding="utf-8") as f:
                return json.load(f)
    for fallback in ["march_2026_fixtures.json", "fixtures_2026.json"]:
        p = base_dir / fallback
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    return []

def run_ingestion(script_path, date, venue, race_no, timeout=180):
    """Runs a single ingestion step as a subprocess."""
    cmd = [sys.executable, script_path, "--date", date, "--venue", venue, "--race", str(race_no)]
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            print(f"[WARN] {script_path} R{race_no} exited {result.returncode}: {result.stderr[:200]}")
        else:
            print(result.stdout.strip()[:300])
        return race_no, result.returncode == 0
    except Exception as e:
        print(f"[ERROR] {script_path} R{race_no}: {e}")
        return race_no, False

def detect_race_count(venue: str, date_str: str) -> int:
    date_compact = date_str.replace("-", "")
    data_dir = Path("data")
    existing = list(data_dir.glob(f"racecard_{date_compact}_R*.json"))
    if existing:
        return max(int(p.stem.split("_R")[-1]) for p in existing)
    return 10 if venue == "ST" else 9

def is_meeting_processed(date_str, venue):
    """Checks if the first race prediction exists for the meeting."""
    # Normalize date for file check
    pred_file = Path("data/predictions") / f"prediction_{date_str}_{venue}_R1.json"
    return pred_file.exists()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="HKJC Master Orchestrator")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--venue", type=str, default=None)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--race", type=int, default=None)
    parser.add_argument("--auto", action="store_true", help="Automatically discover and process upcoming meetings")
    args = parser.parse_args()

    fixtures = load_fixtures(date_str=args.date)
    
    meetings_to_process = []
    
    if args.auto:
        print("\n--- Running in AUTO-DISCOVERY mode ---")
        now = datetime.now().date()
        for f in fixtures:
            try:
                # Fixture date format is DD/MM/YYYY
                f_dt = datetime.strptime(f["date"], "%d/%m/%Y").date()
                f_str = f_dt.strftime("%Y-%m-%d")
                
                # Look ahead 7 days
                if now <= f_dt <= now + timedelta(days=7):
                    if not is_meeting_processed(f_str, f["venue"]):
                        print(f"[FOUND] Upcoming meeting: {f_str} ({f['venue']})")
                        meetings_to_process.append({"date": f_str, "venue": f["venue"]})
            except Exception as e:
                continue
    else:
        # Manual mode for specific date/venue
        target_dt = datetime.strptime(args.date, "%Y-%m-%d")
        target_str = target_dt.strftime("%d/%m/%Y")
        day_fixtures = [f for f in fixtures if f["date"] == target_str]
        for f in day_fixtures:
            meetings_to_process.append({"date": args.date, "venue": args.venue or f["venue"]})

    if not meetings_to_process:
        print("No meetings to process at this time.")
        return

    services_dir = Path(__file__).resolve().parent
    for meeting in meetings_to_process:
        date_str = meeting["date"]
        venue = meeting["venue"]
        max_races = detect_race_count(venue, date_str)
        races_to_run = [args.race] if args.race else range(1, max_races + 1)
        
        print(f"\nProcessing race day: {date_str} at {venue}")

        # 0. Weather Intelligence
        print(f"\n--- [1/3] Generating Weather Intelligence for {venue} ---")
        run_ingestion(str(services_dir / "generate_weather_intel.py"), date_str, venue, 1)

        # 1. Racecard ingestion (All races)
        print(f"\n--- [2/3] Ingesting Racecards ({len(races_to_run)} races) ---")
        # racecard_ingest uses YYYY/MM/DD format in some cases, but the script handles it.
        # We'll run them in a loop or parallel if workers > 1
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(run_ingestion, str(services_dir / "racecard_ingest.py"), date_str.replace("-", "/"), venue, r) for r in races_to_run]
            for future in as_completed(futures):
                pass 

        # 2. AI Prediction (All races)
        print(f"\n--- [3/3] Generating AI Predictions ({len(races_to_run)} races) ---")
        # Prediction engine needs careful rate limiting, so we'll run sequentially for now
        for r in races_to_run:
            run_ingestion(str(services_dir / "prediction_engine.py"), date_str, venue, r)

    print("\nDaily run complete.")

if __name__ == "__main__":
    from datetime import timedelta
    main()
