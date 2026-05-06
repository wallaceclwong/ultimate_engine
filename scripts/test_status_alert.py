import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()
print("\n--- Testing --status on VM ---")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --status 2>&1")
print(out if out else "(no output)")
