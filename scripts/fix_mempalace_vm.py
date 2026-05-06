import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("\n--- Checking pip for mempalace variants ---")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/pip list 2>&1 | grep -i mem")
print(out if out else "(nothing found)")

print("\n--- Checking if mempalace exists as local package ---")
out = m._execute_cmd("find /root -name 'mempalace' -type d 2>/dev/null | head -10")
print(out if out else "(not found)")

out = m._execute_cmd("find /root -name 'setup.py' -path '*/mempalace*' 2>/dev/null")
print(out if out else "(no setup.py)")

print("\n--- Checking pip cache / site-packages ---")
out = m._execute_cmd("find /root/ultimate_engine/.venv -name '*.egg-info' | grep -i mem")
print(out if out else "(no egg-info)")

print("\n--- Checking what check_mempalace does in scheduler ---")
out = m._execute_cmd("grep -n 'mempalace\|get_status\|check_mem' /root/ultimate_engine/ultimate_scheduler_vm.py | head -20")
print(out if out else "(no match)")
