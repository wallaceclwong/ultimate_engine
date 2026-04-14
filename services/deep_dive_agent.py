import os
import sys
import json
from google import genai
from google.genai import types
from pathlib import Path
from loguru import logger

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.weathernext_client import WeatherNextClient
from services.firestore_service import FirestoreService
from config.settings import Config

class DeepDiveAgent:
    def __init__(self):
        self.client = genai.Client(
            vertexai=True,
            project=Config.MODEL_PROJECT_ID,
            location=Config.GCP_LOCATION
        )
        self.model_id = "gemini-2.0-pro-exp-02-05" # Always use Pro for deep dives
        self.firestore = FirestoreService()
        self.weather = WeatherNextClient()
        self.base_dir = Path(__file__).resolve().parent.parent
        self.reports_dir = self.base_dir / "data" / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    async def generate_report(self, card, saddle_number: int):
        """
        Performs an 'Extreme Reasoning' deep dive on a single horse.
        Focuses on qualitative form, pedigree suitability, and weather impact.
        """
        logger.info(f"🔍 DEEP DIVE AGENT: Starting analysis for {card.date} R{card.race_no} Horse #{saddle_number}")
        
        # 1. Fetch Weather Intel
        weather_intel = await self.weather.get_hkjc_forecast(card.venue)
        
        # 2. Construct a specialized deep-dive prompt
        prompt = self._construct_deep_dive_prompt(card, saddle_number, weather_intel)
        
        try:
            # We use DeepSeek-R1 logic here via the Vertex AI / GenAI client if configured, 
            # or simply use Gemini 2.0 Pro for the Reasoning step.
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7, 
                    max_output_tokens=4096
                )
            )
            
            report_text = response.text
            
            # Save the report
            report_path = self.reports_dir / f"deep_dive_{card.date}_R{card.race_no}_S{saddle_number}.md"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(f"# Deep Dive Analysis: {card.date} Race {card.race_no} Horse #{saddle_number}\n\n")
                f.write(report_text)
            
            logger.info(f"✅ DEEP DIVE COMPLETE: Report saved to {report_path}")
            return report_text
            
        except Exception as e:
            logger.error(f"❌ DEEP DIVE FAILED: {e}")
            return f"Reasoning Error: {str(e)}"

    def _construct_deep_dive_prompt(self, card, saddle_number: int, weather_intel) -> str:
        horse = next((h for h in card.horses if h.saddle_number == saddle_number), None)
        if not horse:
            return "Horse not found in racecard."
            
        weather_block = "N/A"
        if weather_intel:
            weather_block = f"""
- Max Temp: {weather_intel.max_temp_c}C
- Prob. Rain: {weather_intel.prob_rain:.0%}
- Forecast: {weather_intel.track_condition_forecast}
- Context: {weather_intel.reasoning}
"""

        prompt = f"""
Act as a Senior Hong Kong Staging Analyst. Your task is to perform an EXTREME REASONING deep dive into one specific horse (# {saddle_number}) in Race {card.race_no} on {card.date}.

### THE HORSE: {horse.horse_name} (# {saddle_number})
- Jockey: {horse.jockey}
- Trainer: {horse.trainer}
- Barrier: {horse.draw}
- Weight: {horse.weight}
- Last 6: {horse.last_6}

### RACE CONTEXT
- Distance: {card.distance}m
- Track: {card.track_type}
- Class: {card.race_class}
- Venue: {card.venue}

### 🌤️ WEATHER INTEL
{weather_block}

### HISTORICAL REASONING TASK
1. **Analyze Past 6 Runs**: Look for 'Sectional Flashes'. Did this horse gain 5+ lengths in the final 400m in any recent run?
2. **Scrutinize Stewards' Reports**: Search for 'Hampered', 'Blocked', 'Raced Wide', or 'Heat Stress' incidents.
3. **Pedigree Check**: Is this specific distance and track type mathematically supported by its heritage?
4. **Jockey Strategy**: Does the current jockey specialize in 'Lead and Hold' or 'Back-marker Swoop'?
5. **Weather & Track Suitability**: How does the predicted weather impact this horse's performance today?

### OUTPUT FORMAT:
Provide a 5-paragraph Senior Staging Report. 
1. **Historical Forgiveness**: List any past runs that the AI should 'ignore'.
2. **Hidden Form**: Identify any 'sectional strengths' not visible in the plain numbers.
3. **Risk Factors**: Identify the #1 reason this horse might LOSE today.
4. **Strategy Verdict**: Final tactical assessment (Primary Pick, Save, or Avoid).
5. **Final Confidence**: 0-100%

CRITICAL: DO NOT use placeholders. Analyze the provided data strictly.
"""
        return prompt
