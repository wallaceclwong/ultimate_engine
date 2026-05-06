import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("\n--- Is scrape/predict still running? ---")
out = m._execute_cmd("ps aux | grep -E 'smart_racecard|predict_today|scheduler_vm' | grep -v grep")
print(out if out else "(nothing running)")

print("\n--- Run noon scrape BLOCKING (wait for completion) ---")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /root/ultimate_engine/scripts/smart_racecard_fetcher.py 2>&1")
print(out[:2000] if out else "(no output)")

print("\n--- Racecards created? ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/ | grep 20260506")
print(out if out else "(none)")

print("\n--- Now run predict ---")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /root/ultimate_engine/predict_today.py 2026-05-06 ST 2>&1 | tail -20")
print(out if out else "(no output)")

print("\n--- Predictions created? ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/predictions/ | grep 20260506")
print(out if out else "(none)")
