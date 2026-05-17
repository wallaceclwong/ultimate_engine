import json
from pathlib import Path
from datetime import datetime

fixtures = json.loads(Path("data/fixtures_season.json").read_text())
today = datetime.now().date()

upcoming = []
for f in fixtures:
    for fmt in ["%d/%m/%Y", "%d/%m/%Y"]:
        try:
            day = int(f["date"].split("/")[0])
            month = int(f["date"].split("/")[1])
            year = int(f["date"].split("/")[2])
            d = datetime(year, month, day).date()
            if d >= today:
                upcoming.append((d, f["venue"], f["type"]))
            break
        except (ValueError, IndexError):
            pass

upcoming.sort()
print("Upcoming race days:")
for d, v, t in upcoming[:6]:
    label = "Day  " if t == "D" else "Night"
    days_away = (d - today).days
    tag = " ← NEXT" if days_away == min((x[0] - today).days for x in upcoming) else ""
    print(f"  {d.strftime('%a %d %b %Y')}  {v}  {label}  ({days_away}d away){tag}")
