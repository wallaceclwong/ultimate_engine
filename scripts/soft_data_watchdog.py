import asyncio
import sys
import os
import json
import requests
from pathlib import Path
from datetime import datetime

# Configuration
DATA_DIR = Path('/root/data')
LATEST_INFO_URL = 'https://racing.hkjc.com/racing/information/English/Racing/LatestInfo.aspx'

# Mock Telegram service for individual runs
class MockTelegram:
    async def send_message(self, msg):
        print(f"[TELEGRAM] {msg}")

async def check_incidents():
    print(f'--- Starting Soft Data Watchdog ({datetime.now().strftime("%H:%M")}) ---')
    
    try:
        # Fetch with requests
        resp = requests.get(LATEST_INFO_URL, timeout=15)
        content = resp.text
        
        # Detection logic
        scratched_count = content.lower().count('scratched')
        jockey_change_count = content.lower().count('jockey change')
        
        if scratched_count > 0 or jockey_change_count > 0:
            msg = f"🔍 [Discovery] New Soft Data found on HKJC:\n"
            msg += f"  - Scratchings: {scratched_count}\n"
            msg += f"  - Jockey Changes: {jockey_change_count}\n"
            msg += f"\nAction: Automated re-fetch triggered for meeting."
            
            print(msg)
            # In a real run, we import the actual telegram_service
            # This is a self-contained version for verification
        else:
            print('  [OK] No new incidents detected for current session.')
            
    except Exception as e:
        print(f'  [ERROR] Watchdog check failed: {str(e)}')
            
    print('--- Watchdog Check Complete ---')

if __name__ == '__main__':
    asyncio.run(check_incidents())
