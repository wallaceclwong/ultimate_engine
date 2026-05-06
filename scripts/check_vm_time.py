import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("\n--- Server time & timezone ---")
out = m._execute_cmd("date && timedatectl | head -5")
print(out if out else "(no output)")

print("\n--- Did predict produce output? ---")
out = m._execute_cmd("ls -lh /root/ultimate_engine/data/predictions/ | grep 20260506 | head -20")
print(out if out else "(no predictions for today)")

print("\n--- Did noon scrape get racecards? ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/ | grep 20260506")
print(out if out else "(no racecard files)")

print("\n--- Telegram .env check ---")
out = m._execute_cmd("grep -c 'TELEGRAM' /root/ultimate_engine/.env 2>/dev/null")
print("Telegram vars in .env:", out.strip() if out else "0")

print("\n--- Last 30 lines of log ---")
out = m._execute_cmd("tail -30 /root/ultimate_engine/automation.log")
print(out if out else "(no output)")
