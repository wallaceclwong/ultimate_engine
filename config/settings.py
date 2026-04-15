from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent

    # ── DeepSeek AI (replaces Google Gemini / Vertex AI) ──────────────────────
    DEEPSEEK_API_KEY   = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL  = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL     = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")      # fast, structured output
    DEEPSEEK_MODEL_R1  = os.getenv("DEEPSEEK_MODEL_R1", "deepseek-reasoner")  # heavy reasoning tasks

    # ── Legacy AI aliases (Google AI disabled, mapped to DeepSeek) ──────────────
    GEMINI_MODEL          = DEEPSEEK_MODEL   # maps old references → DeepSeek
    GEMINI_MODEL_FALLBACK = DEEPSEEK_MODEL   # same
    SHADOW_MODEL          = ""               # disabled
    USE_VERTEX_AI         = False            # Vertex AI disabled

    # ── GCP Cloud Services (non-AI: Firestore, GCS, FCM) ─────────────────────
    # Google AI is OFF, but GCP infrastructure services remain active.
    GCP_LOCATION         = os.getenv("GCP_REGION", "asia-east1")
    PROJECT_ID           = os.getenv("GCP_PROJECT_ID", "ultimate-engine-2026")
    MODEL_PROJECT_ID     = PROJECT_ID  # alias
    GCS_BUCKET_NAME      = os.getenv("GCS_BUCKET_NAME", "ultimate-engine-2026-vault")
    FIRESTORE_DATABASE   = os.getenv("FIRESTORE_DATABASE", "(default)")
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS",
        str(Path(__file__).resolve().parent / "ultimate-engine-sa-key.json")
    )
    
    # --- Betting Account (User must fill these in .env) ---
    HKJC_ACCOUNT = os.getenv("HKJC_ACCOUNT", "YOUR_ACCOUNT_ID")
    HKJC_PASSWORD = os.getenv("HKJC_PASSWORD", "YOUR_PASSWORD")
    
    # --- Prediction Settings ---
    BROWSER_TIMEOUT = 30000  # 30 seconds
    
    # Kelly Criterion Config
    INITIAL_BANKROLL = 9000.0
    KELLY_FRACTION = 0.10  # "Tenth-Kelly" for safe real-money start
    MIN_CONFIDENCE = 0.50  # Only bet if AI confidence > 50%
    MIN_EDGE = 0.05  # Minimum 5% edge required
    
    @staticmethod
    def get_dynamic_confidence(race_class=None, field_size=None, track_condition=None, distance=None):
        """
        Calculate dynamic confidence threshold based on race conditions.
        
        Args:
            race_class: Race class (1-5, where 5 is lowest) - can be string or int
            field_size: Number of horses in the race
            track_condition: Track condition (GOOD, YIELDING, SOFT, WET)
            distance: Race distance in meters
        
        Returns:
            float: Dynamic confidence threshold (0.3 - 0.6)
        """
        base = 0.35  # Start at 35% (more aggressive than current 50%)
        
        # Convert race_class to int if it's a string
        if race_class:
            try:
                race_class = int(str(race_class).replace('CLASS', '').replace('C', ''))
            except (ValueError, AttributeError):
                race_class = None
        
        # Lower class = more upsets = higher confidence needed
        if race_class and race_class >= 4:
            base += 0.10  # Class 4-5 are more unpredictable
        
        # Larger fields = more uncertainty = higher confidence needed
        if field_size and field_size > 12:
            base += 0.05  # Large fields (>12 horses)
        elif field_size and field_size < 8:
            base -= 0.05  # Small fields (<8 horses) - more predictable
        
        # Wet track = more unpredictable = higher confidence needed
        if track_condition and track_condition.upper() in ["WET", "SOFT", "YIELDING"]:
            base += 0.10  # Wet/slow tracks increase uncertainty
        
        # Very short distances (<1000m) = more upsets
        if distance and distance < 1000:
            base += 0.05
        
        # Very long distances (>2000m) = more stamina tests = higher confidence needed
        if distance and distance > 2000:
            base += 0.05
        
        # Ensure confidence stays within reasonable bounds
        return max(0.30, min(0.60, base))
    
    # Track-specific adjustments
    TRACK_KELLY_MULTIPLIERS = {
        "ST": 1.0,   # Sha Tin - baseline
        "HV": 0.85   # Happy Valley - more conservative
    }
    
    # Distance filters (meters)
    MIN_DISTANCE = 1000
    MAX_DISTANCE = 2400
    
    # Odds movement protection
    MAX_ODDS_MOVEMENT = 0.30  # Freeze bet if odds moved > 30% in last update
    
    # Model agreement threshold
    SHADOW_AGREEMENT_THRESHOLD = 0.10  # Models must agree within 10%
    
    # Collections
    COL_FIXTURES = "fixtures"
    COL_RACECARDS = "racecards"
    COL_ODDS = "odds"
    COL_PREDICTIONS = "predictions"
    COL_ANALYTICAL = "analytical"
    COL_RESULTS = "results"
    COL_WEATHER = "weather_intel"
    COL_MARKET_ALERTS = "market_alerts"
    COL_REPORTS = "meeting_reports"
    COL_BANKROLL = "bankroll"

    # Backfill Config
    BACKFILL_BATCH_SIZE = 5
    BACKFILL_DELAY = 5000  # 5 seconds between meetings

    @classmethod
    def get_firestore_client(cls):
        """Returns a live Firestore client using the GCP service account."""
        try:
            from google.cloud import firestore
            import google.auth
            if cls.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(cls.GOOGLE_APPLICATION_CREDENTIALS):
                from google.oauth2 import service_account
                creds = service_account.Credentials.from_service_account_file(
                    cls.GOOGLE_APPLICATION_CREDENTIALS
                )
                return firestore.Client(project=cls.PROJECT_ID, credentials=creds, database=cls.FIRESTORE_DATABASE)
            else:
                return firestore.Client(project=cls.PROJECT_ID, database=cls.FIRESTORE_DATABASE)
        except Exception as e:
            print(f"[WARN] Firestore client init failed: {e}")
            return None
