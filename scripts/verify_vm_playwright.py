import sys
from pathlib import Path

root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def verify():
    m = MemoryService()
    
    print("\n=== VM Playwright Verification ===")
    
    # Check version
    out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python -m playwright --version 2>&1")
    print(f"Playwright version: {out.strip() if out else 'NOT FOUND'}")
    
    # Check pip list
    out = m._execute_cmd("/root/ultimate_engine/.venv/bin/pip show playwright 2>&1 | grep -E 'Name|Version'")
    print(f"Pip show: {out.strip() if out else 'NOT FOUND'}")
    
    # Full test script written to file to avoid escaping issues
    test_script = """
import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page()
        await pg.goto('https://www.google.com', timeout=15000)
        title = await pg.title()
        await b.close()
        print('BROWSER_OK:', title)

asyncio.run(test())
"""
    # Write test script to VM
    m._execute_cmd(f"cat > /tmp/test_pw.py << 'EOF'\n{test_script}\nEOF")
    out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /tmp/test_pw.py 2>&1")
    print(f"Browser test: {out.strip() if out else '(no output)'}")

if __name__ == "__main__":
    verify()
