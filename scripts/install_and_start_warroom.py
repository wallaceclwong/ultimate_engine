import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("--- Install psutil ---")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/pip install psutil -q && echo OK")
print(out if out else "(no output)")

print("\n--- Start war room ---")
m._execute_cmd(
    "nohup /root/ultimate_engine/.venv/bin/python "
    "/root/ultimate_engine/ultimate_scheduler_vm.py --live "
    "> /root/ultimate_engine/warroom_start.log 2>&1 &"
)
time.sleep(8)

print("\n--- Startup log ---")
out = m._execute_cmd("head -20 /root/ultimate_engine/warroom_start.log")
print(out if out else "(no log)")

print("\n--- War room running? ---")
out = m._execute_cmd("ps aux | grep 'scheduler_vm.*--live' | grep -v grep")
print(out if out else "NOT RUNNING")
