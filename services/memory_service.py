import subprocess
import os
import json
import paramiko
import socket
from pathlib import Path
from typing import List, Dict, Any, Optional

class MemoryService:
    """
    Interfaces with the MemPalace vector memory service on the Vultr VM.
    Enables semantic long-term memory for the Ultimate Engine.
    Optimized for production: uses direct execution if on the VM, otherwise use SSH.
    """
    def __init__(self, vm_ip: str = "45.32.255.155", user: str = "root", password: str = "6{tJs[Dhe,jv3@_G"):
        self.vm_ip = vm_ip
        self.user = user
        self.password = password
        self.venv_bin = "/root/mempalace_venv/bin"
        self.wing = "ultimate_engine_2026"
        
        # Detect if we are running on the VM itself
        try:
            hostname = socket.gethostname()
            local_ips = socket.gethostbyname_ex(hostname)[2]
            self.is_on_vm = self.vm_ip in local_ips or "vultr" in hostname.lower()
        except:
            self.is_on_vm = False

    def _execute_cmd(self, cmd: str) -> str:
        """Executes a command either locally (if on VM) or via SSH."""
        # Hardcode thread limiters to prevent segfaults on low-resource machines
        env_cmd = f"export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; {cmd}"
        
        if self.is_on_vm:
            try:
                result = subprocess.run(env_cmd, shell=True, capture_output=True, text=True, timeout=30)
                return result.stdout
            except Exception as e:
                print(f"[MEMORY ERROR] Local Execution Failed: {e}")
                return ""
        else:
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(self.vm_ip, username=self.user, password=self.password, timeout=10)
                stdin, stdout, stderr = ssh.exec_command(env_cmd, timeout=30)
                out = stdout.read().decode(errors="ignore")
                ssh.close()
                return out
            except Exception as e:
                print(f"[MEMORY ERROR] SSH Connection Failed: {e}")
                return ""

    def init_palace(self, remote_dir: str = "/root/ultimate_engine/data"):
        """Initializes the rooms on the VM."""
        print(f"[MEMORY] Initializing palace {remote_dir}...")
        cmd = f"{self.venv_bin}/python -m mempalace.cli init {remote_dir} --yes"
        return self._execute_cmd(cmd)

    def mine(self, remote_dir: str = "/root/ultimate_engine/data"):
        """Mines files into the vector store."""
        print(f"[MEMORY] Mining intelligence from {remote_dir}...")
        cmd = f"cd /root/ultimate_engine && {self.venv_bin}/python -m mempalace.cli mine {remote_dir} --wing {self.wing}"
        return self._execute_cmd(cmd)

    def search(self, query: str, limit: int = 3) -> str:
        """Search the palace for relevant historical context."""
        # Sanitize query for shell
        safe_query = query.replace('"', '\\"')
        cmd = f"{self.venv_bin}/python -m mempalace.cli search \"{safe_query}\" --wing {self.wing} --results {limit}"
        return self._execute_cmd(cmd)

    def get_status(self):
        """Show current filing status."""
        cmd = f"{self.venv_bin}/python -m mempalace.cli status"
        return self._execute_cmd(cmd)

# Singleton Instance
memory_service = MemoryService()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "--status":
            print(memory_service.get_status())
        elif sys.argv[1] == "--search":
            q = sys.argv[2] if len(sys.argv) > 2 else "horse performance"
            print(memory_service.search(q))
