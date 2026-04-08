import subprocess
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

class MemoryService:
    """
    Interfaces with the MemPalace vector memory service on the Vultr VM.
    Enables semantic long-term memory for the Ultimate Engine.
    """
    def __init__(self, vm_ip: str = "100.109.76.69", user: str = "root"):
        self.vm_ip = vm_ip
        self.user = user
        self.venv_bin = "/root/mempalace_venv/bin"
        self.wing = "ultimate_engine_2026"

    def _execute_remote(self, cmd: List[str]) -> str:
        """Helper to run commands on the VM via SSH."""
        remote_cmd = " ".join(cmd)
        full_ssh_cmd = ["ssh", f"{self.user}@{self.vm_ip}", remote_cmd]
        
        try:
            # Use utf-8 encoding to avoid gbk/latin-1 issues on Windows VMs
            result = subprocess.run(full_ssh_cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='ignore')
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"[MEMORY ERROR] SSH Execution Failed: {e.stderr}")
            return ""

    def init_palace(self, remote_dir: str = "/root/ultimate_engine/data"):
        """Initializes the rooms on the VM."""
        # Note: We assume data is synced to the VM or the VM has access to the storage
        print(f"[MEMORY] Initializing palace room structure in {remote_dir}...")
        return self._execute_remote([f"{self.venv_bin}/python", "-m", "mempalace.cli", "init", remote_dir, "--wing", self.wing])

    def mine(self, remote_dir: str = "/root/ultimate_engine/data"):
        """Mines files into the vector store."""
        print(f"[MEMORY] Mining intelligence from {remote_dir}...")
        # We ensure a background process doesn't hang the SSH session
        return self._execute_remote([f"nohup {self.venv_bin}/python", "-m", "mempalace.cli", "mine", remote_dir, "--wing", self.wing, "> /root/mempalace_auto_mine.log 2>&1 &"])

    def search(self, query: str, limit: int = 3) -> str:
        """Search the palace for relevant historical context."""
        print(f"[MEMORY] Searching for: '{query}'...")
        # We use a simplified search bridge via SSH
        return self._execute_remote([f"{self.venv_bin}/python", "-m", "mempalace.cli", "search", f"\"{query}\"", "--wing", self.wing])

    def get_status(self):
        """Show current filing status."""
        return self._execute_remote([f"{self.venv_bin}/python", "-m", "mempalace.cli", "status"])

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
