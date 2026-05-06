import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()
out = m._execute_cmd("cd /root/ultimate_engine && git pull origin main 2>&1 && grep 'TEMPERATURE' predict_today.py")
print(out if out else "(no output)")
