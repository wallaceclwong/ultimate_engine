"""
WeatherAnalyzer — rewritten to use DeepSeek + Open-Meteo.
Google AI removed, but GCP Cloud Services (Firestore) restored.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from openai import OpenAI
from loguru import logger

sys.path.append(os.getcwd())
try:
    from config.settings import Config
    from services.weathernext_client import WeatherNextClient
    from services.firestore_service import FirestoreService
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from config.settings import Config
    from services.weathernext_client import WeatherNextClient
    from services.firestore_service import FirestoreService


class WeatherAnalyzer:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.DEEPSEEK_API_KEY,
            base_url=Config.DEEPSEEK_BASE_URL,
        )
        self.model_id = Config.DEEPSEEK_MODEL
        self.firestore = FirestoreService()
        self.weathernext = WeatherNextClient()

    def get_latest_hko_weather(self):
        weather_dir = Path("data/weather")
        files = list(weather_dir.glob("weather_*.json"))
        if not files:
            return {}
        latest = max(files, key=lambda p: p.stat().st_mtime)
        with open(latest, "r", encoding="utf-8") as f:
            return json.load(f)

    async def analyze(self, venue: str = "HV", date_str: str = None):
        hko_data    = self.get_latest_hko_weather()
        target_date = date_str or datetime.now().strftime("%Y-%m-%d")

        # Fetch Open-Meteo forecast
        logger.info(f"Fetching Open-Meteo forecast for {venue}...")
        wn2_data = await self.weathernext.get_hkjc_forecast(venue)

        prob_context = ""
        if wn2_data:
            prob_context = (
                f"Open-Meteo Forecast:\n"
                f"  Max Temp: {wn2_data.max_temp_c:.1f}°C\n"
                f"  Rain Probability: {wn2_data.prob_rain:.1%}\n"
                f"  P(Temp > 30°C): {wn2_data.prob_temp_above_30:.1%}\n"
                f"  Wind: {wn2_data.wind_speed_kmh:.0f} km/h\n"
                f"  Humidity: {wn2_data.humidity_pct:.0f}%\n"
            )
            logger.info(f"[INFO] Open-Meteo: {wn2_data.description}")

        logger.info(f"Analyzing weather for {venue} on {target_date} using DeepSeek reasoning...")

        prompt = (
            f"You are a Hong Kong horse racing weather expert.\n"
            f"Analyze the following weather data for a race meeting at {venue} on {target_date}.\n\n"
            f"HKO Context: {json.dumps(hko_data)}\n\n"
            f"{prob_context}\n"
            f"Return ONLY a valid JSON object with these exact fields:\n"
            f'{{"venue": "{venue}", "date": "{target_date}", '
            f'"max_temp_c": <float>, "prob_rain": <float 0-1>, '
            f'"prob_temp_above_30": <float 0-1>, '
            f'"track_condition_forecast": "<string e.g. Good|Good to Yielding|Soft>", '
            f'"reasoning": "<brief string>", '
            f'"fetched_at": "<ISO timestamp>"}}'
        )

        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=512,
        )

        intel = json.loads(response.choices[0].message.content)
        intel["fetched_at"] = datetime.now(timezone.utc).isoformat()

        # Save locally
        weather_dir = Config.BASE_DIR / "data" / "weather"
        weather_dir.mkdir(parents=True, exist_ok=True)
        filename = weather_dir / f"intel_{venue}_{target_date}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(intel, f, indent=2)

        # Sync to Firestore
        try:
            doc_id = f"{target_date}_{venue}"
            self.firestore.upsert("weather_intel", doc_id, intel)
            logger.info(f"✅ Weather Intelligence synced to Firestore: {doc_id}")
        except Exception as e:
            logger.error(f"❌ Firestore sync failed: {e}")

        logger.info(f"Weather Intelligence saved to {filename}")
        return intel


if __name__ == "__main__":
    import asyncio
    import argparse

    parser = argparse.ArgumentParser(description="Weather Analyzer (DeepSeek + Open-Meteo)")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--venue", type=str, default="HV")
    args = parser.parse_args()

    analyzer = WeatherAnalyzer()
    asyncio.run(analyzer.analyze(venue=args.venue, date_str=args.date))
