import os
import sys
import firebase_admin
from firebase_admin import credentials, messaging
from typing import Dict, Any, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config

class NotificationService:
    def __init__(self):
        # Initialize Firebase Admin SDK using the same service account
        if not firebase_admin._apps:
            if Config.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(Config.GOOGLE_APPLICATION_CREDENTIALS):
                cred = credentials.Certificate(Config.GOOGLE_APPLICATION_CREDENTIALS)
            else:
                # Fallback to Application Default Credentials (for Cloud Run)
                cred = credentials.ApplicationDefault()
                
            firebase_admin.initialize_app(cred, {
                'projectId': Config.PROJECT_ID
            })
        print(f"[INFO] Firebase Admin initialized: {Config.PROJECT_ID}")

    def send_bet_alert(self, race_id: str, horse_name: str, confidence: float, ev: float, topic: str = "high_confidence_bets"):
        """
        Sends a high-priority push notification for a significant betting opportunity.
        """
        message = messaging.Message(
            notification=messaging.Notification(
                title=f"🚀 HIGH CONFIDENCE: {horse_name}",
                body=f"Race: {race_id} | Confidence: {confidence*100:.1f}% | EV: {ev*100:.1f}%\nOpen dashboard to stage bet."
            ),
            data={
                "race_id": race_id,
                "horse_name": horse_name,
                "confidence": str(confidence),
                "ev": str(ev)
            },
            topic=topic,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    color='#f44336',
                    icon='stock_ticker_update',
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(badge=1),
                ),
            ),
        )

        try:
            response = messaging.send(message)
            print(f"[SUCCESS] Sent notification for {race_id}: {response}")
            return response
        except Exception as e:
            print(f"[ERROR] Failed to send notification: {e}")
            return None

if __name__ == "__main__":
    # Test notification
    service = NotificationService()
    # Note: Topic is used here; in production, you can target specific tokens
    service.send_bet_alert("TEST_RACE", "WINNING_HORSE", 0.95, 0.25)
