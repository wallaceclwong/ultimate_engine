import sys
from pathlib import Path

root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def test():
    m = MemoryService()
    
    print("\n=== Testing HKJC Access from VM ===")
    
    # First check VM's public IP
    print("\n--- VM Public IP ---")
    out = m._execute_cmd("curl -s https://ipinfo.io/json 2>&1 | head -10")
    print(out if out else "(no output)")

    # Write test script to VM
    test_script = '''import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page()
        
        # Test 1: HKJC racing main page
        print("\\nTest 1: HKJC Racing main page...")
        try:
            r = await pg.goto("https://racing.hkjc.com/", timeout=20000)
            print(f"  Status: {r.status} | Title: {await pg.title()}")
        except Exception as e:
            print(f"  FAILED: {e}")
        
        # Test 2: Racecard page
        print("\\nTest 2: HKJC Racecard page...")
        try:
            r = await pg.goto("https://racing.hkjc.com/en-us/local/information/racecard?racedate=2026/05/03&Racecourse=ST&RaceNo=1", timeout=20000)
            print(f"  Status: {r.status} | Title: {await pg.title()}")
            content = await pg.content()
            if "blocked" in content.lower() or "captcha" in content.lower() or "403" in content.lower():
                print("  !! BLOCKED or CAPTCHA detected")
            else:
                print("  OK - no block detected")
        except Exception as e:
            print(f"  FAILED: {e}")

        # Test 3: HKJC betting odds page
        print("\\nTest 3: HKJC Bet odds page...")
        try:
            r = await pg.goto("https://bet.hkjc.com/en/racing/wp/2026-05-03/ST/1", timeout=20000)
            print(f"  Status: {r.status} | Title: {await pg.title()}")
            content = await pg.content()
            if "blocked" in content.lower() or "captcha" in content.lower() or "403" in content.lower():
                print("  !! BLOCKED or CAPTCHA detected")
            else:
                print("  OK - no block detected")
        except Exception as e:
            print(f"  FAILED: {e}")
        
        await b.close()

asyncio.run(test())
'''
    m._execute_cmd("cat > /tmp/test_hkjc.py << 'PYEOF'\n" + test_script + "\nPYEOF")
    print("\n--- HKJC Access Test ---")
    out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /tmp/test_hkjc.py 2>&1")
    print(out if out else "(no output)")

if __name__ == "__main__":
    test()
