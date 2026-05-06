import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("\n--- Pull latest code ---")
out = m._execute_cmd("cd /root/ultimate_engine && git pull origin main 2>&1")
print(out if out else "(no output)")

print("\n--- Run noon scrape NOW ---")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --noon >> /root/ultimate_engine/automation.log 2>&1 &")
print("Noon scrape started in background")

import time; time.sleep(30)

print("\n--- Run predict NOW ---")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --predict >> /root/ultimate_engine/automation.log 2>&1 &")
print("Predict started in background")

import time; time.sleep(5)

print("\n--- Last 15 lines of log ---")
out = m._execute_cmd("tail -15 /root/ultimate_engine/automation.log")
print(out if out else "(no output)")
