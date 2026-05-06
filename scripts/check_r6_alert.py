import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("--- War room log around R6 time (20:45-21:20) ---")
out = m._execute_cmd("grep -E '20:4|20:5|21:0|21:1|21:2|R6|race 6|Race 6' /root/ultimate_engine/automation.log | head -40")
print(out if out else "(nothing)")

print("\n--- War room log around R6 time (warroom_start.log) ---")
out = m._execute_cmd("grep -E '20:4|20:5|21:0|21:1|R6' /root/ultimate_engine/warroom_start.log 2>/dev/null | head -40")
print(out if out else "(nothing)")

print("\n--- Was war room alive at 21:00? Check full log 20:30-21:30 ---")
out = m._execute_cmd("grep -E '\[2026-05-06 2[01]' /root/ultimate_engine/automation.log | head -50")
print(out if out else "(nothing in that window)")

print("\n--- Audited races from scheduler state ---")
out = m._execute_cmd("cat /root/ultimate_engine/scheduler_state.json 2>/dev/null || cat /root/ultimate_engine/logs/scheduler_state.json 2>/dev/null")
print(out if out else "(no state file)")
