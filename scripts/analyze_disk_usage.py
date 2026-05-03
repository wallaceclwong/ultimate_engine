import sys
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def analyze_disk_usage():
    """Analyze disk usage on Vultr VM"""
    mem = MemoryService()
    
    print("\n=== DISK USAGE ANALYSIS ===")
    print("=" * 60)
    
    commands = [
        ("du -sh /root/* 2>/dev/null | sort -hr", "Root directory usage"),
        ("du -sh /root/ultimate_engine/* 2>/dev/null | sort -hr", "Ultimate Engine directory usage"),
        ("du -sh /root/ultimate_engine/data/* 2>/dev/null | sort -hr", "Data directory usage"),
        ("du -sh /root/mempalace_venv 2>/dev/null", "Mempalace venv"),
        ("du -sh /root/.mempalace 2>/dev/null", "Mempalace palace directory"),
        ("df -h", "Overall disk usage"),
    ]
    
    for cmd, description in commands:
        print(f"\n--- {description} ---")
        output = mem._execute_cmd(cmd)
        if output:
            print(output)
        else:
            print("(No output)")

if __name__ == "__main__":
    analyze_disk_usage()
