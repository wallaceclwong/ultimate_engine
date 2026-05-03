import sys
from pathlib import Path

root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def check():
    m = MemoryService()
    
    print("\n=== VM Scraping Capability Check ===")
    
    cmds = [
        ("which chromium-browser || which chromium || echo 'no chromium'", "Chromium binary"),
        ("/root/ultimate_engine/.venv/bin/python -c 'import playwright; print(playwright.__version__)' 2>&1", "Playwright installed"),
        ("ls /root/.cache/ms-playwright/ 2>/dev/null | head -5 || echo 'no playwright browsers'", "Playwright browsers cached"),
        ("/root/ultimate_engine/.venv/bin/python -m playwright install --dry-run 2>&1 | head -5", "Playwright install status"),
        ("cat /root/ultimate_engine/automation.log 2>/dev/null | tail -20", "Recent automation log"),
    ]
    
    for cmd, label in cmds:
        print(f"\n--- {label} ---")
        out = m._execute_cmd(cmd)
        print(out if out else "(no output)")

if __name__ == "__main__":
    check()
