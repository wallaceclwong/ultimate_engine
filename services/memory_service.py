import subprocess
import os
import json
import shlex
import asyncio
try:
    import paramiko
except ImportError:
    paramiko = None
import socket
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent.absolute()
load_dotenv(BASE_DIR / ".env")

class MemoryService:
    """
    Interfaces with the MemPalace vector memory service on the Vultr VM.
    Enables semantic long-term memory for the Ultimate Engine.
    Optimized for production: uses direct execution if on the VM, otherwise use SSH.
    """
    def __init__(self, vm_ip: str = None, user: str = None, password: str = None):
        self.vm_ip = vm_ip or os.getenv("MEMPALACE_SSH_HOST", "100.109.76.69")
        self.user = user or os.getenv("MEMPALACE_SSH_USER", "root")
        self.password = password or os.getenv("MEMPALACE_SSH_PASSWORD", "")
        self.venv_bin = "/root/mempalace_venv/bin"
        self.wing = "ultimate_engine_2026"

        # Detect if we are running on the VM itself
        self.is_on_vm = False
        try:
            def _resolve():
                hostname = socket.gethostname()
                local_ips = socket.gethostbyname_ex(hostname)[2]
                if self.vm_ip in local_ips or "vultr" in hostname.lower():
                    self.is_on_vm = True
            t = threading.Thread(target=_resolve, daemon=True)
            t.start()
            t.join(timeout=2)
        except Exception:
            pass

    def _execute_local(self, args: list, timeout: int = 60, cwd: str = None) -> str:
        """Execute a command locally using subprocess with list args (no shell)."""
        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = "1"
        env["MKL_NUM_THREADS"] = "1"
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env, cwd=cwd)
            return result.stdout
        except Exception as e:
            print(f"[MEMORY ERROR] Local Execution Failed: {e}")
            return ""

    def _execute_ssh(self, args: list, timeout: int = 30) -> str:
        """Execute a command via SSH using properly escaped arguments."""
        if paramiko is None:
            print("[MEMORY ERROR] paramiko not installed — cannot SSH to VM from this host.")
            return ""
        try:
            # Build a shell command with shlex.quote to prevent injection
            quoted_args = " ".join(shlex.quote(a) for a in args)
            env_prefix = "export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1; "
            cmd = env_prefix + quoted_args

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.vm_ip, username=self.user, password=self.password, timeout=10)
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
            out = stdout.read().decode(errors="ignore")
            ssh.close()
            return out
        except Exception as e:
            print(f"[MEMORY ERROR] SSH Connection Failed: {e}")
            return ""

    def _execute_cmd(self, args: list) -> str:
        """Executes a command either locally (if on VM) or via SSH."""
        if self.is_on_vm:
            return self._execute_local(args)
        else:
            return self._execute_ssh(args)

    async def _execute_async(self, args: list) -> str:
        """Async wrapper that runs the blocking command in a thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._execute_cmd, args)

    def init_palace(self, remote_dir: str = "/root/ultimate_engine/data"):
        """Initializes the rooms on the VM."""
        print(f"[MEMORY] Initializing palace {remote_dir}...")
        args = [f"{self.venv_bin}/python", "-m", "mempalace.cli", "init", remote_dir, "--yes"]
        return self._execute_cmd(args)

    def mine(self, remote_dir: str = "/root/ultimate_engine/data"):
        """Mines files into the vector store."""
        print(f"[MEMORY] Mining intelligence from {remote_dir}...")
        args = [
            f"{self.venv_bin}/python", "-m", "mempalace.cli", "mine", remote_dir,
            "--wing", self.wing
        ]
        if self.is_on_vm:
            return self._execute_local(args, cwd="/root/ultimate_engine")
        else:
            # SSH: chain cd with the command
            quoted_args = " ".join(shlex.quote(a) for a in args)
            return self._execute_ssh(["bash", "-c", f"cd /root/ultimate_engine && {quoted_args}"])

    def search(self, query: str, limit: int = 3) -> str:
        """Search the palace for relevant historical context (synchronous)."""
        args = [
            f"{self.venv_bin}/python", "-m", "mempalace.cli", "search", query,
            "--wing", self.wing, "--results", str(limit)
        ]
        return self._execute_cmd(args)

    async def search_async(self, query: str, limit: int = 3) -> str:
        """Search the palace for relevant historical context (async)."""
        args = [
            f"{self.venv_bin}/python", "-m", "mempalace.cli", "search", query,
            "--wing", self.wing, "--results", str(limit)
        ]
        return await self._execute_async(args)

    def get_status(self):
        """Show current filing status."""
        args = [f"{self.venv_bin}/python", "-m", "mempalace.cli", "status"]
        return self._execute_cmd(args)

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
