import os
import time
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timedelta

def get_age_days(path):
    return (time.time() - os.path.getmtime(path)) / (24 * 3600)

def housekeeping(env="vm", dry_run=False):
    print(f"--- HKJC HOUSEKEEPING (Environment: {env.upper()}) ---")
    if dry_run: print("[DRY RUN] No files will be deleted or moved.")
    
    from config.settings import Config
    base_dir = Config.BASE_DIR
    
    # 1. Retention Rules
    if env == "vm":
        TEMP_DAYS = 3
        ARCHIVE_DAYS = 3
        ODDS_DAYS = 7
        WEATHER_DAYS = 30
        ARCHIVE_SCRIPTS = True
    else: # PC
        TEMP_DAYS = 14
        ARCHIVE_DAYS = 14
        ODDS_DAYS = 30
        WEATHER_DAYS = 30
        ARCHIVE_SCRIPTS = False

    # 2. Clean tmp/
    tmp_dir = base_dir / "tmp"
    if tmp_dir.exists():
        print(f"\nScanning {tmp_dir}...")
        for item in tmp_dir.iterdir():
            if get_age_days(item) > TEMP_DAYS:
                print(f"  Cleaning old temp: {item.name}")
                if not dry_run:
                    if item.is_dir(): shutil.rmtree(item)
                    else: item.unlink()

    # 3. Clean Root Archives
    for ext in ["*.tar", "*.tar.gz", "*.zip"]:
        for f in base_dir.glob(ext):
            if get_age_days(f) > ARCHIVE_DAYS:
                print(f"  Cleaning old archive: {f.name}")
                if not dry_run: f.unlink()

    # 4. Clean Data Snapshots
    odds_dir = base_dir / "data" / "odds"
    if odds_dir.exists():
        print(f"\nScanning {odds_dir}...")
        for f in odds_dir.glob("snapshot_*.json"):
            if get_age_days(f) > ODDS_DAYS:
                print(f"  Cleaning old odds: {f.name}")
                if not dry_run: f.unlink()
                
    weather_dir = base_dir / "data" / "weather"
    if weather_dir.exists():
        print(f"\nScanning {weather_dir}...")
        for f in weather_dir.glob("intel_*.json"):
            if get_age_days(f) > WEATHER_DAYS:
                print(f"  Cleaning old weather: {f.name}")
                if not dry_run: f.unlink()

    # 5. Archive One-off Scripts (VM Only)
    if ARCHIVE_SCRIPTS:
        archive_dir = base_dir / "data" / "archive" / "scripts"
        os.makedirs(archive_dir, exist_ok=True)
        print(f"\nScanning for one-off scripts in root...")
        for pattern in ["test_*.py", "run_*.py"]:
            for f in base_dir.glob(pattern):
                # Don't move tracked files (if possible) - here we just assume root scripts are one-offs
                print(f"  Archiving script: {f.name}")
                if not dry_run:
                    shutil.move(str(f), str(archive_dir / f.name))

    print("\nHousekeeping complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HKJC Project Housekeeping")
    parser.add_argument("--env", choices=["pc", "vm"], default="vm", help="Environment ruleset")
    parser.add_argument("--dry-run", action="store_true", help="Don't delete anything")
    args = parser.parse_args()
    
    housekeeping(env=args.env, dry_run=args.dry_run)
