import os
import shutil
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Configuration
DATA_DIR = Path('/root/data')
ARCHIVE_DIR = DATA_DIR / 'archive'
LOG_FILES = [
    '/var/log/hkjc.log',
    '/var/log/hkjc_daily.log',
    '/var/log/hkjc_model_health.log',
    '/root/ultimate_engine/automation.log'
]

# Limits (Days)
ARCHIVE_DAYS = 30
PURGE_DAYS = 180

def get_file_age_days(file_path):
    return (time.time() - os.path.getmtime(file_path)) / (24 * 3600)

def rotate_logs(dry_run=False):
    print('[HOUSEKEEPING] Rotating logs...')
    for log_path in LOG_FILES:
        path = Path(log_path)
        if not path.exists():
            continue
            
        if dry_run:
            print(f'  [DRY-RUN] Would rotate: {log_path}')
            continue
            
        # Standard rotation: .log -> .log.1 -> .log.2 ...
        # (Simple implementation: just append timestamp for now)
        timestamp = datetime.now().strftime('%Y%m%d')
        rot_path = path.with_suffix(f'.{timestamp}.log')
        shutil.copy2(path, rot_path)
        with open(path, 'w') as f:
            f.truncate(0)
        print(f'  Rotated {log_path} -> {rot_path.name}')

def archive_data(dry_run=False):
    print(f'[HOUSEKEEPING] Checking data aging in {DATA_DIR}...')
    if not ARCHIVE_DIR.exists():
        if dry_run:
            print(f'  [DRY-RUN] Would create archive dir: {ARCHIVE_DIR}')
        else:
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # Patterns to archive
    patterns = ['racecard_*.json', 'prediction_*.json']
    
    archive_count = 0
    purge_count = 0
    
    now = time.time()
    
    # 1. Archive old active files
    for pattern in patterns:
        for f in DATA_DIR.glob(pattern):
            age = get_file_age_days(f)
            if age > ARCHIVE_DAYS:
                if dry_run:
                    print(f'  [DRY-RUN] Would archive: {f.name} (age: {age:.1f} days)')
                else:
                    shutil.move(str(f), str(ARCHIVE_DIR / f.name))
                archive_count += 1

    # 2. Purge very old archived files
    for f in ARCHIVE_DIR.glob('*'):
        age = get_file_age_days(f)
        if age > PURGE_DAYS:
            if dry_run:
                print(f'  [DRY-RUN] Would purge: {f.name} (age: {age:.1f} days)')
            else:
                f.unlink()
            purge_count += 1
            
    print(f'[HOUSEKEEPING] Finished: Archived {archive_count}, Purged {purge_count}')

def main():
    parser = argparse.ArgumentParser(description='VM Housekeeping Suite')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without modifying files')
    args = parser.parse_args()
    
    print(f'--- Starting Housekeeping ({datetime.now()}) ---')
    rotate_logs(dry_run=args.dry_run)
    archive_data(dry_run=args.dry_run)
    print('--- Housekeeping Complete ---')

if __name__ == '__main__':
    main()
