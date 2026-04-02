import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from google import genai
from google.genai import types
from google.auth.transport.requests import Request
from google.oauth2 import service_account

# Add project root to path
sys.path.append(os.getcwd())
try:
    from config.settings import Config
    from services.weathernext_client import WeatherNextClient
    from services.firestore_service import FirestoreService
except ImportError:
    # Path enrichment for direct execution
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from config.settings import Config
    from services.weathernext_client import WeatherNextClient
    from services.firestore_service import FirestoreService

class WeatherAnalyzer:
    def __init__(self):
        # 1. Initialize Gemini Client
        if Config.USE_VERTEX_AI:
            print(f"[INFO] Initializing Vertex AI Client in {Config.GCP_LOCATION}...")
            self.client = genai.Client(
                vertexai=True,
                project=Config.PROJECT_ID,
                location=Config.GCP_LOCATION
            )
        else:
            print("[INFO] Initializing Standard Gemini Client...")
            self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
            
        self.model_id = Config.GEMINI_MODEL_FALLBACK  # Weather uses standard Flash, not tuned model
        
        # 2. Firestore Sync
        self.firestore = FirestoreService()
        
        # 3. Initialize WeatherNext 2 Client with OAuth
        self.weathernext = WeatherNextClient()
        self._setup_weathernext_auth()

    def _setup_weathernext_auth(self):
        """Acquires OAuth token for WeatherNext 2 using the service account key."""
        key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account-key.json")
        if os.path.exists(key_path):
            try:
                scopes = ["https://www.googleapis.com/auth/cloud-platform"]
                creds = service_account.Credentials.from_service_account_file(key_path, scopes=scopes)
                creds.refresh(Request())
                self.weathernext.set_oauth_token(creds.token)
                print("[INFO] WeatherNext 2 OAuth token acquired.")
            except Exception as e:
                print(f"[ERROR] Failed to set up WeatherNext OAuth: {e}")
        else:
            print("[WARNING] Service account key not found. WeatherNext 2 will fallback to API key.")

    def get_latest_hko_weather(self):
        weather_dir = Path("data/weather")
        files = list(weather_dir.glob("weather_*.json"))
        if not files:
            return {}
        latest = max(files, key=lambda p: p.stat().st_mtime)
        with open(latest, "r", encoding="utf-8") as f:
            return json.load(f)

    async def analyze(self, venue="HV", date_str=None):
        # 1. Get HKO Contextual Data
        hko_data = self.get_latest_hko_weather()
        
        # Determine target date (default to today if not provided)
        target_date = date_str if date_str else datetime.now().strftime('%Y-%m-%d')
        
        # 2. Get WeatherNext 2 Probabilistic Data
        print(f"Fetching WeatherNext 2 probabilistic forecast for {venue}...")
        wn2_data = await self.weathernext.get_hkjc_forecast(venue)
        
        prob_context = ""
        if wn2_data:
            prob_context = f"""
            WeatherNext 2 Probabilities:
            - Max Temp Prediction: {wn2_data.max_temp_c}C
            - Probability of Rain: {wn2_data.prob_rain:.1%}
            - Probability of Temp > 30C: {wn2_data.prob_temp_above_30:.1%}
            """
            print(f"[INFO] Using WeatherNext 2 data: Rain={wn2_data.prob_rain:.1%}")

        print(f"Analyzing weather for {venue} using Gemini (Unified Engine)...")
        
        prompt = f"""
        Analyze the following current weather data for a horse racing event at {venue}, Hong Kong.
        
        HKO Context: {json.dumps(hko_data)}
        {prob_context}
        
        Generate a 'Weather Intelligence' report in JSON format with these fields:
        - venue: {venue}
        - date: {target_date}
        - max_temp_c: (float) Final predicted max temp (prioritize WeatherNext 2 if available)
        - prob_rain: (float 0.0-1.0) Final probability of rain (prioritize WeatherNext 2 if available)
        - prob_temp_above_30: (float 0.0-1.0) Final probability (prioritize WeatherNext 2 if available)
        - track_condition_forecast: (string, e.g., "Good", "Good to Yielding", "Soft")
        - reasoning: (string) Explanatory summary. Mention the confidence from WeatherNext 2 data if available.
        - fetched_at: (ISO timestamp)
        
        Current context: Humidity {hko_data.get('humidity', 'N/A')}%.
        JSON ONLY.
        """

        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        intel = json.loads(response.text)
        intel["fetched_at"] = datetime.now(timezone.utc).isoformat()
        
        # 4. Save locally
        weather_dir = Config.BASE_DIR / "data/weather"
        weather_dir.mkdir(parents=True, exist_ok=True)
        filename = weather_dir / f"intel_{venue}_{target_date}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(intel, f, indent=2)
            
        # 5. Sync to Firestore (Prod Cloud)
        try:
            doc_id = f"{intel['date']}_{venue}"
            self.firestore.upsert("weather_intel", doc_id, intel)
            print(f"[INFO] Weather Intelligence synced to Firestore: weather_intel/{doc_id}")
        except Exception as e:
            print(f"[WARNING] Firestore sync failed: {e}")

        print(f"Weather Intelligence saved to {filename}")
        return intel

if __name__ == "__main__":
    import asyncio
    import argparse
    
    parser = argparse.ArgumentParser(description="HKJC Weather Intelligence (Unified Engine)")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"),
                        help="Date in YYYY-MM-DD format")
    parser.add_argument("--venue", type=str, default="HV",
                        help="Venue (ST or HV)")
    parser.add_argument("--race", type=int, default=1, help="Ignored (for daily_runner compatibility)")
    
    args = parser.parse_args()
    
    analyzer = WeatherAnalyzer()
    asyncio.run(analyzer.analyze(venue=args.venue, date_str=args.date))
