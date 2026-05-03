import sys
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def check_ram_swap():
    """Check RAM and swapfile usage"""
    mem = MemoryService()
    
    print("\n=== CHECKING RAM AND SWAP ===")
    print("=" * 60)
    
    commands = [
        ("free -h", "RAM and swap usage"),
        ("swapon --show", "Swap file details"),
        ("cat /proc/meminfo | grep -E 'MemTotal|MemAvailable|SwapTotal|SwapFree'", "Memory info"),
    ]
    
    for cmd, description in commands:
        print(f"\n--- {description} ---")
        output = mem._execute_cmd(cmd)
        if output:
            print(output)
        else:
            print("(No output)")

if __name__ == "__main__":
    check_ram_swap()
