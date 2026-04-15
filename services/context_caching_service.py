"""
ContextCachingService — DEPRECATED
====================================
This service previously used Google Vertex AI context caching (Gemini API).
Google AI has been fully removed from the Ultimate Engine. USE_VERTEX_AI=False.

This file is kept as a tombstone to avoid import errors in any legacy code paths.
Do NOT re-enable without explicit approval.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config

class ContextCachingService:
    """DEPRECATED: Vertex AI context caching. Raises on init — Google AI removed."""
    def __init__(self):
        raise NotImplementedError(
            "[ContextCachingService] DISABLED — Google Vertex AI has been removed. "
            "All AI inference now runs via DeepSeek-R1."
        )

    def gather_historical_context(self, num_meetings=5) -> str:
        """
        Gathers results from the last N meetings to serve as a high-density context.
        """
        results_dir = self.data_dir / "results"
        if not results_dir.exists():
            return "No historical results available."

        # Find most recent result files
        files = sorted(list(results_dir.glob("results_*.json")), key=lambda p: p.stat().st_mtime, reverse=True)
        
        # Group by date to get 'num_meetings'
        meetings = {}
        for f in files:
            # results_2024-09-18_HV_R1.json -> 2024-09-18
            try:
                date_part = f.name.split("_")[1]
                if date_part not in meetings:
                    meetings[date_part] = []
                if len(meetings) > num_meetings: 
                    del meetings[date_part]
                    break
                meetings[date_part].append(f)
            except: continue

        context_data = []
        for date_str, m_files in meetings.items():
            meeting_data = {"date": date_str, "races": []}
            for f in m_files:
                try:
                    with open(f, "r", encoding="utf-8") as f_in:
                        meeting_data["races"].append(json.load(f_in))
                except: continue
            context_data.append(meeting_data)

        # Also add Synergy and Steward data summaries if possible
        # For simplicity, we just return the JSON string of the meetings
        return json.dumps(context_data, indent=2)

    def create_meeting_cache(self, meeting_date_str: str, venue: str) -> str:
        """
        Creates a dedicated cache for a specific meeting.
        Includes Historical Context + Common Track/Weather data + System Instructions.
        """
        print(f"[CACHE] Creating context cache for {meeting_date_str} at {venue}...")
        
        history = self.gather_historical_context(num_meetings=8)
        
        system_instruction = f"""
        Act as a professional Hong Kong horse racing analyst. 
        You have access to a large 'Historical Context' of the last 8 meetings.
        Use this to identify:
        1. Jockey-Trainer combo trends.
        2. Horse weight/fitness patterns.
        3. Track bias and sectional performance.
        
        When a specific race is provided, cross-reference it with this historical data.
        """
        
        # The content to cache: System Instruction + Historical Context
        # Note: In the new google-genai SDK, context caching is created for a model and a set of contents.
        
        contents = [
            types.Content(
                role="user",
                parts=[types.Part(text=f"HISTORICAL CONTEXT:\n{history}")]
            )
        ]
        
        try:
            cache = self.client.caches.create(
                model=Config.GEMINI_MODEL,
                config=types.CreateCachedContentConfig(
                    display_name=f"HKJC_Meeting_{meeting_date_str.replace('-', '')}",
                    system_instruction=types.Content(
                        role="system",
                        parts=[types.Part(text=system_instruction)]
                    ),
                    contents=contents,
                    ttl="21600s" # 6 hours (standard meet duration)
                )
            )
            print(f"[CACHE] Success! Cache Name: {cache.name}")
            return cache.name
        except Exception as e:
            print(f"[CACHE] ERROR: {e}")
            return None

    def list_caches(self):
        """Lists active caches."""
        try:
            for cache in self.client.caches.list():
                print(f"- {cache.display_name} ({cache.name}): Exp {cache.expire_time}")
        except Exception as e:
            print(f"[CACHE] List failed: {e}")

    def delete_cache(self, cache_name: str):
        """Deletes a specific cache."""
        try:
            self.client.caches.delete(name=cache_name)
            print(f"[CACHE] Deleted {cache_name}")
        except Exception as e:
            print(f"[CACHE] Delete failed: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--venue", type=str, default="ST")
    args = parser.parse_args()
    
    svc = ContextCachingService()
    cache_name = svc.create_meeting_cache(args.date, args.venue)
    if cache_name:
        print(f"CACHE_NAME={cache_name}")
