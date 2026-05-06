import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("\n--- Find 'LUNAR LEAP' on VM ---")
out = m._execute_cmd("grep -r 'LUNAR LEAP' /root/ultimate_engine/ 2>/dev/null | head -20")
print(out if out else "(not found)")

print("\n--- Find 'War Room started with issues' ---")
out = m._execute_cmd("grep -r 'War Room started' /root/ultimate_engine/ 2>/dev/null | head -10")
print(out if out else "(not found)")

print("\n--- Find 'War Room started' anywhere on VM ---")
out = m._execute_cmd("grep -r 'War Room started' /root/ 2>/dev/null | head -10")
print(out if out else "(not found)")

print("\n--- List Python scripts in /root (not in ultimate_engine) ---")
out = m._execute_cmd("find /root -maxdepth 1 -name '*.py' 2>/dev/null")
print(out if out else "(none)")
