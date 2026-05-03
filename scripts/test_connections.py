import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from consensus_agent import consensus_agent
from services.memory_service import MemoryService

async def test_deepseek():
    print("\n=== Testing DeepSeek Connection ===")
    try:
        is_healthy = await consensus_agent.check_health()
        if is_healthy:
            print("✓ DeepSeek API: CONNECTED")
            return True
        else:
            print("✗ DeepSeek API: FAILED")
            return False
    except Exception as e:
        print(f"✗ DeepSeek API: ERROR - {e}")
        return False

def test_mempalace():
    print("\n=== Testing Mempalace Connection ===")
    try:
        mem = MemoryService()
        status = mem.get_status()
        if status:
            print("✓ Mempalace SSH: CONNECTED")
            print(f"Status: {status}")
            return True
        else:
            print("✗ Mempalace SSH: FAILED")
            return False
    except Exception as e:
        print(f"✗ Mempalace SSH: ERROR - {e}")
        return False

async def main():
    print("\nAI Services Connection Check")
    print("=" * 50)
    
    ds_ok = await test_deepseek()
    mp_ok = test_mempalace()
    
    print("\n=== Summary ===")
    print(f"DeepSeek: {'✓ CONNECTED' if ds_ok else '✗ DISCONNECTED'}")
    print(f"Mempalace: {'✓ CONNECTED' if mp_ok else '✗ DISCONNECTED'}")

if __name__ == "__main__":
    asyncio.run(main())
