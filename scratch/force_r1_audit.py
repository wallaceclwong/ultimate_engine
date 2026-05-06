import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from services.live_audit_service import live_audit_service
from config.settings import Config

async def force_audit():
    print("--- FORCING RACE 1 AUDIT ---")
    today_iso = "2026-04-15"
    venue = "HV"
    
    # Audit Top Candidates for R1
    # 5: MACANESE MASTER (Best Bet)
    # 1: COUNTRY DANCER (Favourite)
    # 9: ORIENTAL SURPRISE (Value)
    
    for h_no in ["5", "1", "9"]:
        print(f"Auditing Horse #{h_no}...")
        try:
            res = await live_audit_service.audit_late_money("2026-04-15_HV_R1", h_no, today_iso, venue, 1)
            print(f"Result for #{h_no}: {res}")
        except Exception as e:
            print(f"Error auditing #{h_no}: {e}")

if __name__ == "__main__":
    asyncio.run(force_audit())
