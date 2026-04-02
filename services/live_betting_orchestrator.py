import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.racecard_ingest import RacecardIngest
from services.odds_ingest import OddsIngest
from services.prediction_engine import PredictionEngine
from services.betslip_service import BetslipService
from services.context_caching_service import ContextCachingService
from config.settings import Config

class LiveBettingOrchestrator:
    def __init__(self, date_str: str, venue: str, num_races: int = None):
        self.date_str = date_str  # Expected in YYYY/MM/DD or YYYY-MM-DD format
        self.venue = venue.upper()
        # Auto-detect race count: 9 for HV, 10 for ST
        self.num_races = num_races or (9 if self.venue == "HV" else 10)
        
        self.racecard_ingest = RacecardIngest(headless=True)
        self.odds_monitor = OddsIngest(headless=True)
        self.prediction_engine = PredictionEngine()
        self.betslip_service = BetslipService()
        
        # Normalize date format for file storage (YYYYMMDD)
        date_clean = date_str.replace("/", "").replace("-", "")
        self.file_date = date_clean
        
        # Normalize for URL (YYYY/MM/DD)
        if "-" in date_str:
            parts = date_str.split("-")
            self.url_date = "/".join(parts)
        else:
            self.url_date = date_str
        
        # Normalize for prediction engine (YYYY-MM-DD)
        self.iso_date = date_str.replace("/", "-")
        
    async def prepare_meeting(self):
        """Ingest all racecards for the meeting."""
        print(f"[LIVE] Preparing meeting for {self.iso_date} at {self.venue} ({self.num_races} races)...")
        
        tasks = []
        for r in range(1, self.num_races + 1):
            tasks.append(self._ingest_racecard(r))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        ok = sum(1 for r in results if r is True)
        print(f"[LIVE] Racecard ingestion complete: {ok}/{self.num_races} OK")

        # Create Context Cache for the whole meeting if using Vertex AI
        if Config.USE_VERTEX_AI:
            try:
                caching_svc = ContextCachingService()
                cache_id = caching_svc.create_meeting_cache(self.iso_date, self.venue)
                if cache_id:
                    self.prediction_engine.cache_id = cache_id
                    print(f"[LIVE] Context Cache active for meeting: {cache_id}")
            except Exception as e:
                print(f"[LIVE] Context Caching failed (falling back to standard): {e}")
        
    async def _ingest_racecard(self, race_no: int) -> bool:
        """Ingest a single racecard."""
        try:
            print(f"[LIVE] Ingesting Racecard R{race_no}...")
            card = await self.racecard_ingest.fetch_racecard(self.url_date, self.venue, race_no)
            if card:
                os.makedirs("data", exist_ok=True)
                filename = f"data/racecard_{self.file_date}_R{race_no}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(card.model_dump_json(indent=2))
                print(f"[LIVE] Saved R{race_no} to {filename}")
                return True
            else:
                print(f"[LIVE] Failed to ingest R{race_no}")
                return False
        except Exception as e:
            print(f"[LIVE] Error ingesting R{race_no}: {e}")
            return False

    async def _monitor_for_triggers(self, race_no: int, initial_odds: Dict[str, float]):
        """
        Background monitor for a specific race. 
        Triggers re-analysis if odds drop significantly or weather changes.
        """
        print(f"[LIVE] Trigger monitor active for R{race_no}")
        last_odds = initial_odds
        
        # Monitor for 20 minutes before the race jump
        for _ in range(20): 
            await asyncio.sleep(60)
            
            # 1. Check for Odds Drops (> 15%)
            try:
                current_odds_data = await self.odds_monitor.fetch_odds(race_no, self.venue, close_browser=False)
                if current_odds_data:
                    current_win_odds = current_odds_data.get("win_odds", {})
                    trigger_hit = False
                    for horse_id, price in current_win_odds.items():
                        old_price = last_odds.get(horse_id)
                        if old_price and price < (old_price * 0.85):
                            print(f"[TRIGGER] Significant drop detected for R{race_no} #{horse_id}: {old_price} -> {price}")
                            trigger_hit = True
                            break
                    
                    if trigger_hit:
                        print(f"[TRIGGER] Auto-Refining prediction for R{race_no} due to market move...")
                        new_prediction = await self.prediction_engine.generate_prediction(self.iso_date, self.venue, race_no)
                        if new_prediction:
                            self.betslip_service.stage_bets([new_prediction])
                        break # Only trigger once per race
                    
                    last_odds = current_win_odds
            except: pass

            # 2. Check for Weather Updates (Track Condition)
            # This could be polled less frequently, but we'll check it here for now
            if _ % 5 == 0: # Every 5 minutes
                try:
                    # In a real scenario, we'd check if the track condition string in data/weather/intel_*.json changed
                    pass
                except: pass

    async def start_live_watch(self, target_time_str: str = None):
        """
        Wait until target time, then capture odds and generate predictions.
        target_time_str: "2026-03-18 18:00:00" (YYYY-MM-DD HH:MM:SS)
        If None, runs immediately.
        """
        if target_time_str:
            target_time = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
            while datetime.now() < target_time:
                remaining = target_time - datetime.now()
                print(f"[LIVE] Waiting for betting window... {str(remaining).split('.')[0]} remaining.", end='\r')
                await asyncio.sleep(60)
            print(f"\n[LIVE] Betting Window OPEN: {target_time_str}")
        else:
            print(f"[LIVE] Running predictions immediately (no target time set)")
        
        # 1. Capture final odds & Generate Predictions
        print("[LIVE] Capturing odds and generating predictions...")
        
        for r in range(1, self.num_races + 1):
            try:
                # Capture snapshot for records
                await self.odds_monitor.capture_snapshot(self.iso_date, r, venue=self.venue)
                
                # Fetch current odds for the trigger monitor
                odds_data = await self.odds_monitor.fetch_odds(r, self.venue, close_browser=False)
                initial_win_odds = odds_data.get("win_odds", {}) if odds_data else {}
                
                # Generate Prediction
                prediction = await self.prediction_engine.generate_prediction(self.iso_date, self.venue, r)
                if prediction and prediction.recommended_bet:
                    self.betslip_service.stage_bets([prediction])
                    print(f"[LIVE] R{r}: {prediction.recommended_bet} (Confidence: {prediction.confidence_score*100:.0f}%)")
                    
                    # Start background monitor for this race
                    asyncio.create_task(self._monitor_for_triggers(r, initial_win_odds))
                
            except Exception as e:
                print(f"[LIVE] Error in race R{r} cycle: {e}")
        
        print(f"[LIVE] Initial preparation complete. {self.num_races} races are now onto Auto-Trigger monitor.")
        return True

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="HKJC Live Betting Orchestrator")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y/%m/%d"),
                        help="Date in YYYY/MM/DD format (default: today)")
    parser.add_argument("--venue", type=str, default="HV",
                        help="Venue: ST or HV (default: HV)")
    parser.add_argument("--races", type=int, default=None,
                        help="Number of races (auto-detected from venue if omitted)")
    parser.add_argument("--target-time", type=str, default=None,
                        help="Target time to begin live watch e.g. '2026-03-18 18:00:00'")
    parser.add_argument("--prepare-only", action="store_true",
                        help="Only ingest racecards, do not generate predictions")
    args = parser.parse_args()

    orchestrator = LiveBettingOrchestrator(args.date, args.venue, args.races)
    
    print(f"[LIVE] Starting preparation for {args.date} at {args.venue} ({orchestrator.num_races} races)...")
    await orchestrator.prepare_meeting()
    
    if args.prepare_only:
        print("\n[LIVE] Preparation complete (--prepare-only). Exiting.")
        return
    
    await orchestrator.start_live_watch(target_time_str=args.target_time)
    print("\n[LIVE] All done.")

if __name__ == "__main__":
    asyncio.run(main())
