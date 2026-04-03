import os
import json
import httpx
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict
from loguru import logger
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config

@dataclass
class HKJCWeatherIntelligence:
    venue: str
    date: str
    max_temp_c: float
    prob_rain: float
    prob_temp_above_30: float
    track_condition_forecast: str
    reasoning: str
    fetched_at: datetime

class WeatherNextClient:
    """
    Fetches probabilistic forecasts from Google Maps Weather API (WeatherNext 2 backend)
    specifically for HKJC venues (Sha Tin and Happy Valley).
    """
    BASE_URL = "https://weather.googleapis.com/v1"
    
    VENUES = {
        "ST": {"lat": 22.4014, "lng": 114.2044, "name": "Sha Tin"},
        "HV": {"lat": 22.2721, "lng": 114.1824, "name": "Happy Valley"}
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GMAPS_API_KEY")
        if not self.api_key:
            # Fallback to config if available
            self.api_key = getattr(Config, 'GMAPS_API_KEY', None)
            
        self.oauth_token = None
        self.project_id = Config.PROJECT_ID # Quota project for OAuth
            
        self._client = httpx.AsyncClient(timeout=10.0)

    def set_oauth_token(self, token: str):
        """Enable OAuth authentication instead of API key."""
        self.oauth_token = token
        self.api_key = None

    async def get_hkjc_forecast(self, venue: str) -> Optional[HKJCWeatherIntelligence]:
        """
        Fetch probabilistic forecast for a specific HKJC venue.
        """
        if venue not in self.VENUES:
            logger.error(f"Invalid venue: {venue}")
            return None

        loc = self.VENUES[venue]
        url = f"{self.BASE_URL}/forecast/days:lookup"
        
        params = {
            "location.latitude": loc["lat"],
            "location.longitude": loc["lng"],
            "days": 1,
            "unitsSystem": "METRIC",
        }
        
        headers = {}
        if self.oauth_token:
            headers["Authorization"] = f"Bearer {self.oauth_token}"
            headers["X-Goog-User-Project"] = self.project_id
        else:
            params["key"] = self.api_key

        try:
            resp = await self._client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            day = data.get("forecastDays", [{}])[0]
            daytime = day.get("daytimeForecast", {})
            temp_info = day.get("maxTemperature", {})
            temp_range = day.get("temperatureRange", {})

            max_temp = float(temp_info.get("degrees", 25.0))
            low = float(temp_range.get("minTemperature", {}).get("degrees", max_temp - 2))
            high = float(temp_range.get("maxTemperature", {}).get("degrees", max_temp + 2))
            precip_prob = daytime.get("precipitationProbability", 0) / 100.0

            # Compute P(Temp > 30) using Gaussian spread
            import math
            mean = max_temp
            sigma = (high - low) / (2 * 1.645) # 90% confidence interval
            
            prob_above_30 = 0.0
            if sigma > 0:
                z = (30 - mean) / (sigma * math.sqrt(2))
                p_below = 0.5 * (1 + math.erf(z))
                prob_above_30 = round(1.0 - p_below, 4)
            elif mean > 30:
                prob_above_30 = 1.0

            # Determine Track Condition Forecast
            if precip_prob > 0.6:
                track = "Yielding/Soft (High Confidence of Rain)"
            elif precip_prob > 0.3:
                track = "Good to Yielding (Moderate Rain Risk)"
            else:
                track = "Good / Firm (Dry Forecast)"

            intel = HKJCWeatherIntelligence(
                venue=venue,
                date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                max_temp_c=max_temp,
                prob_rain=precip_prob,
                prob_temp_above_30=prob_above_30,
                track_condition_forecast=track,
                reasoning=f"Forecast max {max_temp}C with {precip_prob:.0%} rain probability at {loc['name']}.",
                fetched_at=datetime.now(timezone.utc)
            )
            
            # Save intelligence to data/weather
            os.makedirs("data/weather", exist_ok=True)
            output_path = f"data/weather/intel_{venue}_{intel.date}.json"
            with open(output_path, "w", encoding="utf-8") as f:
                # Use a dictionary representation for JSON
                intel_dict = {
                    "venue": intel.venue,
                    "date": intel.date,
                    "max_temp_c": intel.max_temp_c,
                    "prob_rain": intel.prob_rain,
                    "prob_temp_above_30": intel.prob_temp_above_30,
                    "track_condition_forecast": intel.track_condition_forecast,
                    "reasoning": intel.reasoning,
                    "fetched_at": intel.fetched_at.isoformat()
                }
                json.dump(intel_dict, f, indent=2)
            
            logger.info(f"Weather Intelligence generated for {venue}: {track}")
            return intel

        except Exception as e:
            logger.exception(f"Error fetching WeatherNext 2 for {venue}: {e}")
            return None

    async def close(self):
        await self._client.aclose()

if __name__ == "__main__":
    async def test():
        client = WeatherNextClient()
        await client.get_hkjc_forecast("ST")
        await client.get_hkjc_forecast("HV")
        await client.close()
    
    asyncio.run(test())
