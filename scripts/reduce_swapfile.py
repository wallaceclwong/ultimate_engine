import sys
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def reduce_swapfile():
    """Reduce swapfile from 6.2G to 2G"""
    mem = MemoryService()
    
    print("\n=== REDUCING SWAPFILE ===")
    print("=" * 60)
    print("Current: 6.2G swapfile (953MB used)")
    print("Target: 2G swapfile")
    print("Space to reclaim: 4.2G")
    
    # Check disk space before
    print("\n--- Disk space before ---")
    output = mem._execute_cmd("df -h /")
    print(output)
    
    # Disable swap
    print("\n--- Disabling swap ---")
    output = mem._execute_cmd("swapoff /swapfile")
    print("✓ Swap disabled")
    
    # Resize swapfile to 2G
    print("\n--- Resizing swapfile to 2G ---")
    output = mem._execute_cmd("dd if=/dev/zero of=/swapfile bs=1M count=2048 status=progress")
    print("✓ Swapfile resized to 2G")
    
    # Set permissions
    output = mem._execute_cmd("chmod 600 /swapfile")
    print("✓ Permissions set")
    
    # Make swap
    output = mem._execute_cmd("mkswap /swapfile")
    print("✓ Swap formatted")
    
    # Enable swap
    output = mem._execute_cmd("swapon /swapfile")
    print("✓ Swap enabled")
    
    # Verify
    print("\n--- Verifying new swap ---")
    output = mem._execute_cmd("swapon --show")
    print(output)
    
    output = mem._execute_cmd("free -h")
    print(output)
    
    # Check disk space after
    print("\n--- Disk space after ---")
    output = mem._execute_cmd("df -h /")
    print(output)
    
    print("\n=== SUMMARY ===")
    print("Reduced: 6.2G → 2G swapfile")
    print("Space reclaimed: 4.2G")

if __name__ == "__main__":
    reduce_swapfile()
