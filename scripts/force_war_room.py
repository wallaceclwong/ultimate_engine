import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("--- Check for lock files ---")
out = m._execute_cmd("ls -la /root/ultimate_engine/*.lock 2>/dev/null")
print(out if out else "(no lock files)")

print("\n--- Remove any lock files ---")
m._execute_cmd("rm -f /root/ultimate_engine/ultimate_scheduler.lock")

print("\n--- Try starting war room, capture startup errors ---")
m._execute_cmd(
    "nohup /root/ultimate_engine/.venv/bin/python "
    "/root/ultimate_engine/ultimate_scheduler_vm.py --live "
    "> /root/ultimate_engine/warroom_start.log 2>&1 &"
)
time.sleep(8)

print("\n--- Startup log ---")
out = m._execute_cmd("cat /root/ultimate_engine/warroom_start.log 2>/dev/null | head -30")
print(out if out else "(no log)")

print("\n--- Process check ---")
out = m._execute_cmd("ps aux | grep 'scheduler_vm' | grep -v grep")
print(out if out else "(nothing)")
