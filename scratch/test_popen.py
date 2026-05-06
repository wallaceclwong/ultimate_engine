import subprocess
import sys
import os
import time
from pathlib import Path

def test_start():
    base_dir = Path(__file__).resolve().parent.parent
    py_exec = sys.executable
    script = base_dir / "ultimate_scheduler_vm.py"
    
    print(f"Executing: {py_exec} {script}")
    
    # Try starting it without --live first to see if it just prints and exits
    # We use CREATE_NEW_CONSOLE for Windows
    proc = subprocess.Popen(
        [py_exec, str(script), "--help"],
        cwd=str(base_dir),
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    
    print(f"Process PID: {proc.pid}")
    time.sleep(2)
    
    # Check if PID still exists
    import psutil
    try:
        p = psutil.Process(proc.pid)
        print(f"Process is alive: {p.status()}")
    except psutil.NoSuchProcess:
        print("Process died immediately.")

if __name__ == "__main__":
    test_start()
