import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()
print("\n--- VM automation log (last 40 lines) ---")
out = m._execute_cmd("tail -40 /root/ultimate_engine/automation.log")
print(out if out else "(no output)")
