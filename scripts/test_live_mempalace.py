import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("\n--- Run check_mempalace() as the scheduler does ---")
script = (
    "import sys, asyncio\n"
    "sys.path.insert(0, '/root/ultimate_engine')\n"
    "from services.memory_service import MemoryService\n"
    "ms = MemoryService()\n"
    "print('is_on_vm:', ms.is_on_vm)\n"
    "status = ms.get_status()\n"
    "print('has WING:', bool(status and 'WING' in status))\n"
    "print('status[:100]:', repr(status[:100]) if status else 'EMPTY')\n"
)
m._execute_cmd("cat > /tmp/chk.py << 'EOF'\n" + script + "\nEOF")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /tmp/chk.py 2>&1")
print(out if out else "(no output)")
