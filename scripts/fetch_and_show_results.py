import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("--- Check prediction R1 structure ---")
out = m._execute_cmd("cat /root/ultimate_engine/data/predictions/prediction_2026-05-06_ST_R1.json | python3 -c \"import sys,json; d=json.load(sys.stdin); print(list(d.keys()))\"")
print(out if out else "(no output)")

print("\n--- Check if learn/results job running ---")
out = m._execute_cmd("ps aux | grep -E 'learn_today|scheduler.*learn' | grep -v grep")
print(out if out else "(not running)")

print("\n--- Check results dir ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/results/ | tail -10")
print(out if out else "(empty)")

print("\n--- Trigger learn now ---")
m._execute_cmd(
    "nohup /root/ultimate_engine/.venv/bin/python "
    "/root/ultimate_engine/ultimate_scheduler_vm.py --learn "
    ">> /root/ultimate_engine/automation.log 2>&1 &"
)
print("Learn job launched — results will be fetched from HKJC")

import time; time.sleep(15)

print("\n--- Results available yet? ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/results/ | grep 20260506 | head -15")
print(out if out else "(not yet, still fetching...)")
