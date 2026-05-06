import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()
out = m._execute_cmd("cat /root/ultimate_engine/data/results/results_2026-05-06_ST_R1.json | python3 -c \"import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2))\" | head -60")
print(out if out else "(no output)")
