import sys
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def check_duplicate():
    """Check if /opt/ultimate_engine is duplicate of /root/ultimate_engine"""
    mem = MemoryService()
    
    print("\n=== CHECKING FOR DUPLICATE ULTIMATE ENGINE ===")
    print("=" * 60)
    
    commands = [
        ("ls -la /opt/ultimate_engine | head -20", "Contents of /opt/ultimate_engine"),
        ("ls -la /root/ultimate_engine | head -20", "Contents of /root/ultimate_engine"),
        ("diff -r /opt/ultimate_engine /root/ultimate_engine 2>&1 | head -50", "Compare directories"),
        ("du -sh /opt/ultimate_engine /root/ultimate_engine", "Size comparison"),
        ("stat /opt/ultimate_engine | grep Modify", "Last modified: /opt"),
        ("stat /root/ultimate_engine | grep Modify", "Last modified: /root"),
    ]
    
    for cmd, description in commands:
        print(f"\n--- {description} ---")
        output = mem._execute_cmd(cmd)
        if output:
            print(output)
        else:
            print("(No output)")

if __name__ == "__main__":
    check_duplicate()
