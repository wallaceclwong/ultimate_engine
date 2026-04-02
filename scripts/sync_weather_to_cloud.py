import os
import json
from pathlib import Path
from services.firestore_service import FirestoreService
from config.settings import Config
from loguru import logger

def sync_weather():
    fs = FirestoreService()
    if not fs.db:
        logger.error("Firestore not initialized. Check credentials.")
        return

    weather_dir = Path("data/weather")
    if not weather_dir.exists():
        logger.warning("No local weather data found in data/weather")
        return

    count = 0
    for w_file in weather_dir.glob("intel_*.json"):
        try:
            with open(w_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Use venue_date as doc ID (e.g., HV_2026-03-25)
            doc_id = f"{data['venue']}_{data['date']}"
            
            # Ensure timestamp exists for 'get_latest' ordering in server.py
            if "timestamp" not in data and "fetched_at" in data:
                data["timestamp"] = data["fetched_at"]
            
            success = fs.upsert(Config.COL_WEATHER, doc_id, data)
            if success:
                logger.info(f"✅ Synced weather: {doc_id}")
                count += 1
        except Exception as e:
            logger.error(f"Failed to sync {w_file.name}: {e}")

    logger.info(f"🏁 Finished. Synced {count} weather documents to Firestore.")

if __name__ == "__main__":
    sync_weather()
