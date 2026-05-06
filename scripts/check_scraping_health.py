import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("--- Racecards for today ---")
out = m._execute_cmd("ls -lh /root/ultimate_engine/data/racecard_20260506_*.json 2>/dev/null")
print(out if out else "(none)")

print("\n--- Odds snapshots for today ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/odds/snapshot_20260506_*.json 2>/dev/null | wc -l")
print(f"{out.strip()} snapshots captured")

print("\n--- Latest odds snapshot content (R1) ---")
out = m._execute_cmd("ls -t /root/ultimate_engine/data/odds/snapshot_20260506_R1_*.json 2>/dev/null | head -1 | xargs cat 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('R1 horses:', len(d.get('win_odds',{})), 'win odds | timestamp:', d.get('timestamp','?'))\"")
print(out if out else "(no R1 snapshot)")

print("\n--- War room process ---")
out = m._execute_cmd("ps aux | grep 'scheduler_vm.*--live' | grep -v grep")
print(out if out else "(NOT RUNNING)")

print("\n--- Prediction files ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/predictions/prediction_20260506_*.json 2>/dev/null | wc -l")
print(f"{out.strip()} predictions ready")
