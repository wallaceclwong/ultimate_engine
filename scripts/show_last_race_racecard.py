import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("=== MAY 13 HV NIGHT — RACECARD ===\n")

# Get racecard files
out = m._execute_cmd("ls /root/ultimate_engine/data/racecards/racecard_2026-05-13_HV_R*.json 2>/dev/null | sort -V | tail -1")
last_race_file = out.strip() if out else None

if not last_race_file:
    print("No racecards found yet. Scraping happens at 12:00 HKT.")
    sys.exit(0)

race_num = last_race_file.split("_R")[-1].replace(".json", "")
print(f"LAST RACE: R{race_num}\n")

# Read the racecard
out = m._execute_cmd(f"cat {last_race_file}")
if not out:
    print("(file empty or unreadable)")
    sys.exit(0)

try:
    rc = json.loads(out)
except json.JSONDecodeError:
    print("(invalid JSON)")
    sys.exit(0)

# Extract key fields
print(f"Race: {rc.get('race_number', '?')}")
print(f"Distance: {rc.get('distance', '?')}m")
print(f"Going: {rc.get('going', '?')}")
print(f"Prize: HK${rc.get('prize_money', '?')}")
print(f"Class: {rc.get('class', '?')}")
print()

# Build table
entries = rc.get('entries', [])
if not entries:
    print("(no entries)")
    sys.exit(0)

print(f"{'#':<3} {'Horse':<28} {'Jockey':<15} {'Trainer':<15} {'Weight':<7} {'Draw':<5}")
print("-" * 80)

for e in entries:
    no = e.get('horse_number', '?')
    name = e.get('horse_name', '?')[:26]
    jockey = e.get('jockey', '?')[:13]
    trainer = e.get('trainer', '?')[:13]
    wt = e.get('declared_weight', '?')
    draw = e.get('draw', '?')
    print(f"{no:<3} {name:<28} {jockey:<15} {trainer:<15} {wt:<7} {draw:<5}")

print(f"\nTotal: {len(entries)} runners")
