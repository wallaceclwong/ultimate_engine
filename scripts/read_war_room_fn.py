import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()
out = m._execute_cmd("grep -n 'run_live_war_room\|mem_ok\|ds_ok\|check_mempalace\|War Room started\|issues' /root/ultimate_engine/ultimate_scheduler_vm.py")
print(out if out else "(no output)")
