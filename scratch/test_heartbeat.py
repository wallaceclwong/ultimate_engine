import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import lunar_heartbeat

async def test_recovery():
    print("--- Testing Watchdog Recovery Logic ---")
    
    # 1. Mock get_today_fixture to simulate a Race Day
    lunar_heartbeat.get_today_fixture = lambda: {'date': '20/04/2026', 'venue': 'ST_TEST'}
    
    # 2. Mock Telegram to verify message sending
    sent_msgs = []
    class MockTelegram:
        async def send_message(self, msg): 
            # Strip emojis for console output to avoid encoding errors
            clean_msg = "".join(c for c in msg if ord(c) < 128)
            print(f"  [TELEGRAM SENT] {clean_msg}")
            sent_msgs.append(msg)
    lunar_heartbeat.telegram_service = MockTelegram()
    
    # 3. Check if scheduler is running (should be False unless user has it open)
    is_running = lunar_heartbeat.is_scheduler_running()
    print(f"  Scheduler running: {is_running}")
    
    if not is_running:
        print("  Triggering Heartbeat...")
        await lunar_heartbeat.run_heartbeat()
        
        # 4. Verify recovery
        if any("Self-Healing" in m for m in sent_msgs):
            print("\n✅ SUCCESS: Watchdog detected missing scheduler and triggered recovery.")
        else:
            print("\n❌ FAILURE: Watchdog did not trigger recovery.")
    else:
        print("  [SKIP] Scheduler is already running. Please close it to test recovery.")

if __name__ == "__main__":
    asyncio.run(test_recovery())
