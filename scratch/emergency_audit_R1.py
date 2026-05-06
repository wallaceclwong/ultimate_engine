import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

async def main():
    from services.live_audit_service import live_audit_service
    from telegram_service import telegram_service
    
    r_no = "1"
    candidates_nos = ['8', '5', '4', '2']
    today_iso = "2026-04-22"
    venue = "HV"
    j_time = "18:40"
    
    print(f"--- EMERGENCY AUDIT: Race {r_no} ---")
    try:
        audit_results = []
        for h_no in candidates_nos:
            print(f"[AUDIT] Checking Horse #{h_no} (R{r_no})...")
            # Trigger live audit via service
            res = await live_audit_service.audit_late_money(f"R{r_no}", h_no, today_iso, venue, int(r_no))
            if res:
                audit_results.append(res)
        
        if audit_results:
            print(f"[SUCCESS] Audit completed with results.")
        else:
            print(f"[INFO] Audit completed. No high-conviction Smart Money detected.")
            await telegram_service.send_message(f"ℹ️ *Lunar Heartbeat*: Race {r_no} audited (EMERGENCY). No high-conviction Smart Money detected.")
            
    except Exception as e:
        print(f"[ERROR] Emergency audit failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
