import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("--- Check predictions with correct filename ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/predictions/ | grep 2026-05-06")
print(out if out else "(none with dashes format)")

print("\n--- Restart war room ---")
m._execute_cmd("pkill -f 'scheduler_vm.*--live' 2>/dev/null; sleep 2")
m._execute_cmd(
    "nohup /root/ultimate_engine/.venv/bin/python "
    "/root/ultimate_engine/ultimate_scheduler_vm.py --live "
    ">> /root/ultimate_engine/automation.log 2>&1 &"
)
time.sleep(5)

print("\n--- Verify war room running ---")
out = m._execute_cmd("ps aux | grep 'scheduler_vm.*--live' | grep -v grep")
print(out if out else "(NOT RUNNING — problem!)")

print("\n--- Also refresh odds snapshot now ---")
m._execute_cmd(
    "nohup /root/ultimate_engine/.venv/bin/python "
    "/root/ultimate_engine/ultimate_scheduler_vm.py --odds "
    ">> /root/ultimate_engine/automation.log 2>&1 &"
)
print("Odds refresh launched in background")
