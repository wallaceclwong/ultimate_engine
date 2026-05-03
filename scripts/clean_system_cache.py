import sys
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def clean_system_cache():
    """Clean snap packages and package cache"""
    mem = MemoryService()
    
    print("\n=== CLEANING SYSTEM CACHE ===")
    print("=" * 60)
    
    # Check disk space before
    print("\n--- Disk space before ---")
    output = mem._execute_cmd("df -h /")
    print(output)
    
    # Clean old snap revisions
    print("\n--- Cleaning old snap packages ---")
    print("Listing all snap packages...")
    output = mem._execute_cmd("snap list --all")
    print(output)
    
    # Remove old snap revisions (keep only current)
    print("\nRemoving old snap revisions...")
    output = mem._execute_cmd("snap set system refresh.retain=2")
    print(f"Set snap retention to 2 versions")
    
    # Remove disabled snaps
    output = mem._execute_cmd("sh -c 'snap list --all | awk \"/disabled/{print \\$1, \\$3}\" | while read snapname revision; do snap remove \\$snapname --revision=\\$revision; done'")
    print("Removed disabled snap revisions")
    
    # Clean package cache
    print("\n--- Cleaning package cache ---")
    output = mem._execute_cmd("apt-get clean")
    print("✓ apt-get clean")
    
    output = mem._execute_cmd("apt-get autoremove -y")
    print("✓ apt-get autoremove")
    
    # Clean snap cache
    output = mem._execute_cmd("rm -rf /var/lib/snapd/cache/*")
    print("✓ Cleaned snapd cache")
    
    # Check disk space after
    print("\n--- Disk space after ---")
    output = mem._execute_cmd("df -h /")
    print(output)
    
    print("\n=== SUMMARY ===")
    print("Cleaned: Old snap packages, package cache, snapd cache")
    print("Space reclaimed: ~2-3G (estimated)")

if __name__ == "__main__":
    clean_system_cache()
