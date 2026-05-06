import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("\n--- Fire scrape in background ---")
m._execute_cmd(
    "nohup /root/ultimate_engine/.venv/bin/python "
    "/root/ultimate_engine/scripts/smart_racecard_fetcher.py "
    "> /root/ultimate_engine/scrape_now.log 2>&1 &"
)
print("Scrape launched. Waiting 3 minutes...")

time.sleep(180)

print("\n--- Racecards created? ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/ | grep 20260506")
print(out if out else "(none — scrape still running?)")

print("\n--- Scrape log tail ---")
out = m._execute_cmd("tail -10 /root/ultimate_engine/scrape_now.log 2>/dev/null")
print(out if out else "(no log)")

print("\n--- Now run predict ---")
m._execute_cmd(
    "nohup /root/ultimate_engine/.venv/bin/python "
    "/root/ultimate_engine/predict_today.py 2026-05-06 ST "
    ">> /root/ultimate_engine/automation.log 2>&1 &"
)
print("Predict launched.")

time.sleep(30)

print("\n--- Predictions created? ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/predictions/ | grep 20260506 | head -5")
print(out if out else "(none yet)")
