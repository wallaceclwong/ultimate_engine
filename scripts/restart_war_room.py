import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("--- Kill existing war room ---")
out = m._execute_cmd("pkill -f 'ultimate_scheduler_vm.py --live' 2>/dev/null; echo done")
print(out)
time.sleep(3)

print("\n--- Check predictions status ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/predictions/ | grep 20260506 | wc -l")
print(f"Prediction files: {out.strip()}")

out = m._execute_cmd("ps aux | grep predict_today | grep -v grep")
print("predict_today running:", out if out else "(not running)")

print("\n--- Run predict synchronously ---")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /root/ultimate_engine/predict_today.py 2026-05-06 ST 2>&1 | tail -15")
print(out if out else "(no output)")

print("\n--- Predictions now ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/predictions/ | grep 20260506")
print(out if out else "(none)")

print("\n--- Restart war room with correct schedule ---")
m._execute_cmd(
    "nohup /root/ultimate_engine/.venv/bin/python "
    "/root/ultimate_engine/ultimate_scheduler_vm.py --live "
    ">> /root/ultimate_engine/automation.log 2>&1 &"
)
print("War room restarted.")
