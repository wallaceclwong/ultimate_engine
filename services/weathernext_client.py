import httpx
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict
from loguru import logger
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config

@dataclass
class WeatherForecast:
    max_temp_c: float
    prob_rain: float          # 0.0 – 1.0
    prob_temp_above_30: float # 0.0 – 1.0
    wind_speed_kmh: float
    humidity_pct: float
    description: str

class WeatherNextClient:
    """Fetches weather from Open-Meteo — free, no API key, no Google."""
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    
    VENUE_COORDS = {
        "HV": {"latitude": 22.2721, "longitude": 114.1824},  # Happy Valley
        "ST": {"latitude": 22.3915, "longitude": 114.1900},  # Sha Tin
    }

    async def get_hkjc_forecast(self, venue: str) -> Optional[WeatherForecast]:
        coords = self.VENUE_COORDS.get(venue, self.VENUE_COORDS["HV"])
        params = {
            "latitude":  coords["latitude"],
            "longitude": coords["longitude"],
            "daily": [
                "temperature_2m_max",
                "precipitation_probability_max",
                "windspeed_10m_max",
            ],
            "hourly": ["relativehumidity_2m"],
            "timezone": "Asia/Hong_Kong",
            "forecast_days": 1,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            daily  = data.get("daily", {})
            hourly = data.get("hourly", {})

            max_temp  = (daily.get("temperature_2m_max") or [25.0])[0]
            rain_prob = (daily.get("precipitation_probability_max") or [10])[0] / 100.0
            wind      = (daily.get("windspeed_10m_max") or [10.0])[0]
            humidity  = sum(hourly.get("relativehumidity_2m") or [75]) / max(len(hourly.get("relativehumidity_2m") or [1]), 1)

            prob_above_30 = max(0.0, min(1.0, (max_temp - 28.0) / 6.0))

            desc = f"Max {max_temp:.1f}°C, rain {rain_prob:.0%}, wind {wind:.0f} km/h, humidity {humidity:.0f}%"
            logger.info(f"[WEATHER] Open-Meteo for {venue}: {desc}")

            return WeatherForecast(
                max_temp_c=max_temp,
                prob_rain=rain_prob,
                prob_temp_above_30=prob_above_30,
                wind_speed_kmh=wind,
                humidity_pct=humidity,
                description=desc,
            )
        except Exception as e:
            logger.error(f"[WEATHER] Open-Meteo fetch failed for {venue}: {e}")
            return None

    def set_oauth_token(self, token: str):
        pass

if __name__ == "__main__":
    async def _test():
        client = WeatherNextClient()
        result = await client.get_hkjc_forecast("HV")
        print(result)
    asyncio.run(_test())
