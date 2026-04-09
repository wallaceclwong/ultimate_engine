import subprocess
import os
import json
import paramiko
from pathlib import Path
from typing import List, Dict, Any, Optional

class MemoryService:
    """
    Interfaces with the MemPalace vector memory service on the Vultr VM.
    Enables semantic long-term memory for the Ultimate Engine.
    Uses paramiko (not subprocess SSH) for reliable cross-platform connectivity.
    """
    def __init__(self, vm_ip: str = "45.32.255.155", user: str = "root", password: str = "6{tJs[Dhe,jv3@_G"):
        self.vm_ip = vm_ip
        self.user = user
        self.password = password
        self.venv_bin = "/root/mempalace_venv/bin"
        self.wing = "ultimate_engine_2026"

    def _execute_remote(self, cmd: str) -> str:
        """Helper to run commands on the VM via paramiko SSH (password auth)."""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.vm_ip, username=self.user, password=self.password, timeout=10)
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=25)
            out = stdout.read().decode(errors="ignore")
            ssh.close()
            return out
        except Exception as e:
            print(f"[MEMORY ERROR] Connection Failed: {e}")
            return ""

    def init_palace(self, remote_dir: str = "/root/ultimate_engine/data"):
        """Initializes the rooms on the VM."""
        print(f"[MEMORY] Initializing palace room structure in {remote_dir}...")
        cmd = f"export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; {self.venv_bin}/python -m mempalace.cli init {remote_dir} --wing {self.wing}"
        return self._execute_remote(cmd)

    def mine(self, remote_dir: str = "/root/ultimate_engine/data"):
        """Mines files into the vector store."""
        print(f"[MEMORY] Mining intelligence from {remote_dir}...")
        cmd = f"export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; cd /root/ultimate_engine && nohup {self.venv_bin}/python -m mempalace.cli mine {remote_dir} --wing {self.wing} > /root/mempalace_auto_mine.log 2>&1 &"
        return self._execute_remote(cmd)

    def search(self, query: str, limit: int = 3) -> str:
        """Search the palace for relevant historical context."""
        print(f"[MEMORY] Searching for: '{query}'...")
        cmd = f"export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; {self.venv_bin}/python -m mempalace.cli search \"{query}\" --wing {self.wing}"
        return self._execute_remote(cmd)

    def get_status(self):
        """Show current filing status."""
        cmd = f"export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; {self.venv_bin}/python -m mempalace.cli status"
        return self._execute_remote(cmd)

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
