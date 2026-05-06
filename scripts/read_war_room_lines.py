import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()
out = m._execute_cmd("sed -n '434,530p' /root/ultimate_engine/ultimate_scheduler_vm.py")
print(out if out else "(no output)")
