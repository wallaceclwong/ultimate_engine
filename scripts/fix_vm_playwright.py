import sys
from pathlib import Path

root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def fix():
    m = MemoryService()
    
    print("\n=== Fixing Playwright on VM ===")
    
    # Install playwright in the venv
    print("\n--- Installing playwright in venv ---")
    out = m._execute_cmd("/root/ultimate_engine/.venv/bin/pip install playwright --quiet")
    print(out if out else "(done)")
    
    # Verify install
    print("\n--- Verifying install ---")
    out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python -c 'import playwright; print(\"playwright OK:\", playwright.__version__)'")
    print(out if out else "(no output)")
    
    # Check if browsers are already linked (existing system chromium)
    print("\n--- Checking browser availability ---")
    out = m._execute_cmd("ls /root/.cache/ms-playwright/")
    print(out if out else "(no cache)")
    
    # Test a quick headless scrape
    print("\n--- Test: quick headless browser launch ---")
    test_cmd = "/root/ultimate_engine/.venv/bin/python -c \"\nimport asyncio\nfrom playwright.async_api import async_playwright\nasync def test():\n    async with async_playwright() as p:\n        b = await p.chromium.launch(headless=True)\n        pg = await b.new_page()\n        await pg.goto('https://www.google.com', timeout=15000)\n        title = await pg.title()\n        await b.close()\n        print('Browser OK. Title:', title)\nasyncio.run(test())\n\""
    out = m._execute_cmd(test_cmd)
    print(out if out else "(no output)")
    
    print("\n=== Done ===")

if __name__ == "__main__":
    fix()
