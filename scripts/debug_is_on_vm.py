import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("\n--- VM hostname and IPs ---")
out = m._execute_cmd("hostname && hostname -I")
print(out if out else "(no output)")

print("\n--- Test is_on_vm detection from VM ---")
test = """
import socket
hostname = socket.gethostname()
local_ips = socket.gethostbyname_ex(hostname)[2]
vm_ip = '100.109.76.69'
is_on_vm = vm_ip in local_ips or 'vultr' in hostname.lower()
print('hostname:', hostname)
print('local_ips:', local_ips)
print('is_on_vm:', is_on_vm)
"""
out = m._execute_cmd(f"/root/mempalace_venv/bin/python -c \"{test}\" 2>&1")
print(out if out else "(no output)")

print("\n--- Test get_status() directly from VM Python ---")
test2 = """
import sys
sys.path.insert(0, '/root/ultimate_engine')
from services.memory_service import MemoryService
ms = MemoryService()
print('is_on_vm:', ms.is_on_vm)
status = ms.get_status()
print('has WING:', 'WING' in status if status else False)
print('status length:', len(status) if status else 0)
"""
out = m._execute_cmd(f"/root/ultimate_engine/.venv/bin/python -c \"{test2}\" 2>&1")
print(out if out else "(no output)")
