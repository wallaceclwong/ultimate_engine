import sys
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def detailed_disk_analysis():
    """Detailed analysis of disk usage including system directories"""
    mem = MemoryService()
    
    print("\n=== DETAILED DISK USAGE ANALYSIS ===")
    print("=" * 60)
    
    commands = [
        ("du -sh /* 2>/dev/null | sort -hr | head -15", "Top 15 root directories"),
        ("du -sh /usr/* 2>/dev/null | sort -hr | head -10", "/usr directory (system packages)"),
        ("du -sh /var/* 2>/dev/null | sort -hr | head -10", "/var directory (logs, cache)"),
        ("du -sh /var/log/* 2>/dev/null | sort -hr | head -10", "/var/log (system logs)"),
        ("du -sh /var/cache/* 2>/dev/null | sort -hr | head -10", "/var/cache (package cache)"),
        ("du -sh /opt/* 2>/dev/null | sort -hr", "/opt directory"),
        ("du -sh /home/* 2>/dev/null | sort -hr", "/home directory"),
    ]
    
    for cmd, description in commands:
        print(f"\n--- {description} ---")
        output = mem._execute_cmd(cmd)
        if output:
            print(output)
        else:
            print("(No output)")

if __name__ == "__main__":
    detailed_disk_analysis()
