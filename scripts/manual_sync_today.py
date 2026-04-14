import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))
from pc_race_day import sync_to_vm

if __name__ == "__main__":
    date_str = "2026-04-12"
    print(f"Executing manual sync for {date_str}...")
    sync_to_vm(date_str)
