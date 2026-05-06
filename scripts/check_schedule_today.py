import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("\n--- get_dynamic_schedule() for today ---")
script = (
    "import sys\n"
    "sys.path.insert(0, '/root/ultimate_engine')\n"
    "from ultimate_scheduler_vm import get_dynamic_schedule, get_today_fixture\n"
    "fxt = get_today_fixture()\n"
    "print('Fixture:', fxt)\n"
    "sched = get_dynamic_schedule()\n"
    "print('Schedule:', sched)\n"
)
m._execute_cmd("cat > /tmp/sched.py << 'EOF'\n" + script + "\nEOF")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /tmp/sched.py 2>&1")
print(out if out else "(no output)")

print("\n--- Check if predict ran and predictions exist ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/predictions/ | grep 20260506")
print(out if out else "(no predictions yet)")

print("\n--- Check racecards ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/ | grep 20260506")
print(out if out else "(no racecards yet)")
