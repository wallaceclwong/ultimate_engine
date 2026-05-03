import sys
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def check_ssh_config():
    """Check SSH configuration and test connection"""
    mem = MemoryService()
    
    print("\n=== SSH CONFIGURATION CHECK ===")
    print("=" * 60)
    print(f"VM IP: {mem.vm_ip}")
    print(f"User: {mem.user}")
    print(f"Is on VM: {mem.is_on_vm}")
    
    # Try to ping the VM
    print("\n--- Testing connectivity ---")
    try:
        import subprocess
        result = subprocess.run(["ping", "-c", "2", mem.vm_ip], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✓ VM is reachable via ping")
            print(result.stdout)
        else:
            print("✗ VM is NOT reachable via ping")
            print(result.stderr)
    except Exception as e:
        print(f"✗ Ping failed: {e}")
    
    # Check if Tailscale is available
    print("\n--- Checking Tailscale ---")
    try:
        result = subprocess.run(["tailscale", "status"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✓ Tailscale is running")
            print(result.stdout[:500])
        else:
            print("✗ Tailscale not available or not running")
    except Exception as e:
        print("✗ Tailscale check failed")

if __name__ == "__main__":
    check_ssh_config()
