import os
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from services.memory_service import memory_service

def main():
    print(f"Mining intelligence from {BASE_DIR / 'data'} into MemPalace...")
    try:
        memory_service.mine(str(BASE_DIR / "data"))
        print("Success: Mining complete.")
    except Exception as e:
        print(f"Error: Mining failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
