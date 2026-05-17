import sys, json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load current fixture
fixtures = json.loads(Path("data/fixtures_season.json").read_text())

# Find and remove May 12
removed = []
kept = []
for f in fixtures:
    try:
        day = int(f["date"].split("/")[0])
        month = int(f["date"].split("/")[1])
        year = int(f["date"].split("/")[2])
        d = datetime(year, month, day).date()
        if d == datetime(2026, 5, 12).date():
            removed.append(f)
        else:
            kept.append(f)
    except (ValueError, IndexError):
        kept.append(f)

if removed:
    print(f"Removing May 12 fixture: {removed}")
    Path("data/fixtures_season.json").write_text(json.dumps(kept, indent=2))
    print("Updated fixtures_season.json")
else:
    print("May 12 not found in fixtures_season.json")

# Also update fixtures_2026.json
f2026 = json.loads(Path("data/fixtures_2026.json").read_text())
removed2 = []
kept2 = []
for f in f2026:
    try:
        day = int(f["date"].split("/")[0])
        month = int(f["date"].split("/")[1])
        year = int(f["date"].split("/")[2])
        d = datetime(year, month, day).date()
        if d == datetime(2026, 5, 12).date():
            removed2.append(f)
        else:
            kept2.append(f)
    except (ValueError, IndexError):
        kept2.append(f)

if removed2:
    print(f"Removing from fixtures_2026.json: {removed2}")
    Path("data/fixtures_2026.json").write_text(json.dumps(kept2, indent=2))
    print("Updated fixtures_2026.json")
else:
    print("May 12 not found in fixtures_2026.json")

# Show next upcoming
print("\nNext upcoming fixtures:")
upcoming = []
today = datetime.now().date()
for f in kept:
    try:
        day = int(f["date"].split("/")[0])
        month = int(f["date"].split("/")[1])
        year = int(f["date"].split("/")[2])
        d = datetime(year, month, day).date()
        if d >= today:
            upcoming.append((d, f["venue"], f["type"]))
    except (ValueError, IndexError): pass
upcoming.sort()
for d, v, t in upcoming[:5]:
    label = "Day" if t == "D" else "Night"
    print(f"  {d.strftime('%a %d %b %Y')}  {v}  {label}")
