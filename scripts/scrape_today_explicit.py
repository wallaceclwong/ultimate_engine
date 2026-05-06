import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

# Build a Python script that scrapes all races for today
fetch_script = """
import asyncio, sys, json, os
sys.path.insert(0, '/root/ultimate_engine')
from services.racecard_ingest import RacecardIngest

async def fetch_all():
    ingest = RacecardIngest(headless=True)
    date_str = '2026/05/06'
    venue = 'ST'
    for r in range(1, 12):
        try:
            print(f'Fetching R{r}...')
            card = await ingest.fetch_racecard(date_str, venue, r)
            if card:
                fname = f'/root/ultimate_engine/data/racecard_20260506_R{r}.json'
                with open(fname, 'w') as f:
                    f.write(card.model_dump_json(indent=2))
                print(f'Saved R{r}')
            else:
                print(f'R{r}: no data')
        except Exception as e:
            print(f'R{r} error: {e}')

asyncio.run(fetch_all())
"""

print("--- Writing and launching scraper ---")
m._execute_cmd("cat > /tmp/fetch_today.py << 'PYEOF'\n" + fetch_script + "\nPYEOF")
m._execute_cmd("nohup /root/ultimate_engine/.venv/bin/python /tmp/fetch_today.py > /root/ultimate_engine/fetch_today.log 2>&1 &")
print("Scraper launched. Waiting 5 minutes...")

time.sleep(300)

print("\n--- Scrape log ---")
out = m._execute_cmd("cat /root/ultimate_engine/fetch_today.log 2>/dev/null")
print(out[:2000] if out else "(no log)")

print("\n--- Racecards created ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/ | grep 20260506")
print(out if out else "(none)")
