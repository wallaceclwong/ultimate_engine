import sys
from pathlib import Path

root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def test():
    m = MemoryService()
    
    print("\n=== Testing Telegram from VM ===")
    
    test_script = """import asyncio, sys
sys.path.insert(0, '/root/ultimate_engine')
from telegram_service import telegram_service

async def test():
    ok = await telegram_service.send_message(
        "🤖 *VM Automation Online*\\n"
        "✅ Playwright installed\\n"
        "✅ Cron jobs active\\n"
        "✅ HKJC access confirmed\\n\\n"
        "Race day schedule:\\n"
        "  09:30 Morning odds scrape\\n"
        "  12:00 Racecard scrape\\n"
        "  13:00 Predictions run\\n"
        "  21:00 Post-race learning\\n\\n"
        "_VM is now the primary race day operator._"
    )
    print("Telegram:", "OK" if ok else "FAILED")

asyncio.run(test())
"""
    m._execute_cmd(f"cat > /tmp/test_tg.py << 'PYEOF'\n{test_script}\nPYEOF")
    out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /tmp/test_tg.py 2>&1")
    print(out if out else "(no output)")

if __name__ == "__main__":
    test()
