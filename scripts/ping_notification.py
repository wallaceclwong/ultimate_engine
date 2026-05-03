"""
Ping Notification Test (Fixed)
Sends a test push via NotificationService to verify FCM connectivity.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from services.notification_service import NotificationService

def ping():
    print("--- Notification Connectivity Test ---")
    notifier = NotificationService()
    
    # Using existing method send_bet_alert which has the push logic
    print("Sending test bet alert via FCM...")
    response = notifier.send_bet_alert(
        race_id="TEST_RACE",
        horse_name="SYSTEM_READY",
        confidence=1.0,
        ev=0.99
    )
    
    if response:
        print(f"✅ PING SUCCESSFUL: Response: {response}")
    else:
        print("❌ PING FAILED: Check logs.")

if __name__ == "__main__":
    ping()
