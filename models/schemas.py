from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

# --- Core Infrastructure Models ---

class Fixture(BaseModel):
    date: datetime
    venue: str  # "ST", "HV"
    day_night: str  # "D", "N"
    race_type: str  # "Local", "Simulcast"
    status: str = "Scheduled"

# --- Horse & Race Card Models ---

class HorseEntry(BaseModel):
    horse_id: str
    horse_name: str
    owner: str
    sire: Optional[str] = None
    dam: Optional[str] = None
    saddle_number: int
    draw: int
    jockey: str
    trainer: str
    weight: float
    optimal_weight_range: Optional[List[float]] = None
    training_location: str = "HK"  # "HK" or "CTC" (Conghua)
    last_6_runs: List[str] = []
    gear: str = ""
    stable_change: bool = False
    trial_comments: Optional[str] = None
    synergy_score: float = 0.0

class RaceCard(BaseModel):
    race_id: str  # YYYY-MM-DD_RACE_XX
    date: datetime
    race_number: int
    distance: int
    track_type: str
    course: str
    race_class: str
    predicted_pace: str = "EVEN"
    jump_time: Optional[str] = None  # Added for scheduler awareness
    horses: List[HorseEntry]

# --- Odds & Market Models ---

class OddsSnapshot(BaseModel):
    race_id: str
    timestamp: datetime
    interval: int  # Minutes relative to jump: 60, 30, 10, 1
    win_odds: Dict[str, float]  # horse_id -> odds
    place_odds: Dict[str, List[float]]  # horse_id -> [min, max]

# --- AI & Learning Models ---

class Prediction(BaseModel):
    race_id: str
    gemini_model: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    is_best_bet: bool = False
    recommended_bet: str = "WIN"
    probabilities: Dict[str, float]
    kelly_stakes: Dict[str, float]
    market_odds: Optional[Dict[str, float]] = None
    analysis_markdown: str

class RaceResult(BaseModel):
    race_id: str
    winners: List[str]  # horse_ids
    placings: List[str]
    win_dividend: float
    place_dividends: List[float]
    incident_reports: Dict[str, str]  # horse_id -> comment

# --- Weather Model ---

class WeatherSnapshot(BaseModel):
    venue: str
    timestamp: datetime
    temp: float
    humidity: int
    rainfall_2h: float
    track_condition: str
