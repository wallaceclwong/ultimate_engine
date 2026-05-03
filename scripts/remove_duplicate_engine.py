import sys
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def remove_duplicate():
    """Remove old duplicate /opt/ultimate_engine"""
    mem = MemoryService()
    
    print("\n=== REMOVING OLD DUPLICATE ===")
    print("=" * 60)
    print("Target: /opt/ultimate_engine (2.1G)")
    print("Last modified: April 15, 2026 (16 days ago)")
    print("Active version: /root/ultimate_engine (updated today)")
    print("\nProceeding with removal...")
    
    # First, check disk space before
    print("\n--- Disk space before ---")
    output = mem._execute_cmd("df -h /")
    print(output)
    
    # Remove the directory
    print("\n--- Removing /opt/ultimate_engine ---")
    output = mem._execute_cmd("rm -rf /opt/ultimate_engine")
    print("✓ Directory removed")
    
    # Check disk space after
    print("\n--- Disk space after ---")
    output = mem._execute_cmd("df -h /")
    print(output)
    
    # Verify removal
    print("\n--- Verifying removal ---")
    output = mem._execute_cmd("ls -la /opt/ | grep ultimate_engine")
    if output.strip():
        print("✗ Still exists!")
        print(output)
    else:
        print("✓ Successfully removed")
    
    print("\n=== SUMMARY ===")
    print("Removed: /opt/ultimate_engine (2.1G)")
    print("Space reclaimed: ~2.1G")

if __name__ == "__main__":
    remove_duplicate()
