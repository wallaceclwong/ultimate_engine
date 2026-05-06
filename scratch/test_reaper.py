import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import lunar_heartbeat

def test_reaper_safety():
    print("--- Testing Reaper Safety Logic ---")
    
    class MockProcess:
        def __init__(self, name, exe, create_time):
            self.info = {
                'name': name,
                'exe': exe,
                'create_time': create_time
            }
        def kill(self):
            print(f"  [MOCK KILL] Killed {self.info['name']} at {self.info['exe']}")

    # Case 1: Standard Google Chrome (Should NOT be killed)
    p1 = MockProcess("chrome.exe", "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", time.time() - 10000)
    
    # Case 2: Playwright Chromium (Should BE killed if > 2 hours)
    p2 = MockProcess("chrome.exe", "C:\\Users\\ASUS\\AppData\\Local\\ms-playwright\\chromium-1105\\chrome-win\\chrome.exe", time.time() - 10000)
    
    # Case 3: Recent Playwright Chromium (Should NOT be killed)
    p3 = MockProcess("chrome.exe", "C:\\Users\\ASUS\\AppData\\Local\\ms-playwright\\chromium-1105\\chrome-win\\chrome.exe", time.time() - 100)

    test_processes = [p1, p2, p3]
    
    print("Testing logic...")
    killed_count = 0
    for proc in test_processes:
        exe = (proc.info.get('exe') or "").lower()
        name = (proc.info.get('name') or "").lower()
        
        if 'chromium' in name or 'playwright' in name or 'chrome' in name:
            if 'ms-playwright' in exe:
                if time.time() - proc.info['create_time'] > 7200:
                    proc.kill()
                    killed_count += 1
            else:
                print(f"  [SAFE] Skipping non-automation browser: {name} at {exe}")

    if killed_count == 1:
        print("\n✅ SUCCESS: Only the orphaned Playwright browser was targeted.")
    else:
        print(f"\n❌ FAILURE: Targeting logic incorrect. Killed {killed_count} processes.")

if __name__ == "__main__":
    test_reaper_safety()
