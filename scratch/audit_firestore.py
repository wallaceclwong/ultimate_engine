import os
import sys
from google.cloud import firestore
from google.oauth2 import service_account
from datetime import datetime, timedelta

def audit():
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'config/ultimate-engine-sa-key.json'
    db = firestore.Client(project='ultimate-engine-2026')

    print('--- Recent Market Alerts (Errors/Panics) ---')
    try:
        # Check alerts from the last 3 days
        three_days_ago = datetime.now() - timedelta(days=3)
        alerts = db.collection('market_alerts').where('timestamp', '>', three_days_ago.isoformat()).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(20).stream()
        
        count = 0
        for a in alerts:
            count += 1
            d = a.to_dict()
            ts = d.get('timestamp', 'N/A')
            alert_type = d.get('type', 'INFO')
            message = d.get('message', 'No message')
            print(f"[{ts}] {alert_type}: {str(message)[:100]}")
        
        if count == 0:
            print("No alerts found in the last 3 days.")
            
    except Exception as e:
        print(f"Alerts query failed: {e}")

    print('\n--- Recent Analytical Logs ---')
    try:
        logs = db.collection('analytical').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
        for l in logs:
            d = l.to_dict()
            ts = d.get('timestamp', 'N/A')
            event = d.get('event', 'N/A')
            status = d.get('status', 'N/A')
            print(f"[{ts}] {event}: {status}")
    except Exception as e:
        print(f"Logs query failed: {e}")

if __name__ == "__main__":
    audit()
