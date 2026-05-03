import sys
from pathlib import Path

root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def install():
    m = MemoryService()
    
    print("\n=== Installing Playwright Chromium on VM ===")
    print("(This may take 1-2 minutes to download...)\n")
    
    out = m._execute_cmd("/root/ultimate_engine/.venv/bin/playwright install chromium 2>&1")
    print(out if out else "(no output)")
    
    print("\n--- Verifying ---")
    out = m._execute_cmd("ls /root/.cache/ms-playwright/")
    print(out if out else "(no output)")
    
    print("\n--- Running browser test ---")
    test = """import asyncio
from playwright.async_api import async_playwright
async def test():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page()
        await pg.goto('https://www.google.com', timeout=20000)
        print('BROWSER_OK:', await pg.title())
        await b.close()
asyncio.run(test())"""
    m._execute_cmd(f"cat > /tmp/test_pw.py << 'PYEOF'\n{test}\nPYEOF")
    out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /tmp/test_pw.py 2>&1")
    print(out if out else "(no output)")

if __name__ == "__main__":
    install()
