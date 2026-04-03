import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from loguru import logger
from typing import Dict, List, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config
from services.odds_ingest import OddsIngest
from services.browser_manager import BrowserManager
from services.firestore_service import FirestoreService
from services.bankroll_manager import BankrollManager

class MarketWatchdog:
    def __init__(self, drop_threshold=0.20):
        """
        drop_threshold: Decimal percentage drop to trigger a 'Smart Money' alert.
        Default is 20% drop.
        """
        self.odds_service = OddsIngest(headless=True)
        self.baselines = {} # {race_id: {horse_no: baseline_odds}}
        self.drop_threshold = drop_threshold
        self.data_dir = Config.BASE_DIR / "data/alerts"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.last_heartbeat = None
        self.firestore = FirestoreService()
        self.bankroll_manager = BankrollManager()
        self._poll_lock = asyncio.Lock()  # Serialize browser access across races

    async def poll_and_detect(self, race_no: int, venue: str = "ST"):
        """
        Polls current odds and detects significant drops compared to baseline.
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        race_id = f"{date_str}_{venue}_R{race_no}"
        
        try:
            async with self._poll_lock:
                logger.info(f"Watchdog polling {race_id}...")
                odds_data = await self.odds_service.fetch_odds(date_str=date_str, race_no=race_no, venue=venue)
            
            if not odds_data:
                logger.warning(f"Watchdog failed to fetch odds for {race_id}")
                return []
            
            self.last_heartbeat = datetime.now().isoformat()
        except Exception as e:
            logger.error(f"Error in poll_and_detect for {race_id}: {e}")
            # Ensure browser is cleaned up after crash
            try:
                await self.odds_service.browser_mgr.stop()
            except Exception:
                pass
            return []

        current_win_odds = odds_data.get("win_odds", {})
        alerts = []

        # Always update prediction files with latest odds
        if current_win_odds:
            self._update_prediction_odds(date_str, venue, race_no, current_win_odds)

        # If we don't have a baseline for this race yet, set it now
        if race_id not in self.baselines:
            self.baselines[race_id] = current_win_odds
            logger.info(f"Baseline set for {race_id}")
            return []

        baseline_win_odds = self.baselines[race_id]

        for horse_no, current_val in current_win_odds.items():
            baseline_val = baseline_win_odds.get(horse_no)
            
            if baseline_val and current_val < baseline_val:
                drop_pct = (baseline_val - current_val) / baseline_val
                
                if drop_pct >= self.drop_threshold:
                    logger.warning(f"🔥 SMART MONEY DETECTED: Race {race_no} Horse {horse_no} dropped {drop_pct*100:.1f}% ({baseline_val} -> {current_val})")
                    
                    alert = {
                        "type": "SMART MONEY",
                        "severity": "high",
                        "horse_no": horse_no,
                        "description": f"Significant odds drop detected: ${baseline_val} to ${current_val} ({drop_pct*100:.1f}% drop).",
                        "implied_prob_change": round((1/current_val - 1/baseline_val) * 100, 2),
                        "timestamp": datetime.now().isoformat()
                    }
                    alerts.append(alert)

        if alerts:
            self._save_alerts(race_id, alerts)
            
        return alerts

    def _save_alerts(self, race_id: str, alerts: List[Dict]):
        alert_file = self.data_dir / f"market_alerts_{race_id}.json"
        
        # Load existing if any
        existing = []
        if alert_file.exists():
            try:
                with open(alert_file, "r", encoding="utf-8") as f:
                    existing = json.load(f).get("alerts", [])
            except: pass

        # Combine and deduplicate by horse_no (keep latest)
        combined = {a["horse_no"]: a for a in (existing + alerts)}
        
        with open(alert_file, "w", encoding="utf-8") as f:
            json.dump({
                "race_id": race_id,
                "updated_at": datetime.now().isoformat(),
                "alerts": list(combined.values())
            }, f, indent=2)
        
        # 3. Sync to Firestore (Dedicated alerts collection)
        try:
            self.firestore.upsert(
                Config.COL_MARKET_ALERTS, 
                race_id, 
                {
                    "race_id": race_id,
                    "updated_at": datetime.now().isoformat(),
                    "alerts": list(combined.values())
                }
            )
            logger.info(f"✅ Market alerts synced to Firestore: {race_id}")
        except Exception as e:
            logger.error(f"⚠️ Failed to sync alerts to Firestore: {e}")

    async def run_loop(self, race_no: int, venue: str = "ST", interval=120):
        """
        Continuous background loop for a specific race.
        Staggered by race_no to avoid all races queuing simultaneously.
        """
        stagger = race_no * 10  # R1=10s, R2=20s, ... R11=110s
        logger.info(f"Starting Watchdog loop for Race {race_no} every {interval}s (stagger {stagger}s)")
        await asyncio.sleep(stagger)
        while True:
            try:
                await self.poll_and_detect(race_no, venue)
            except Exception as e:
                logger.error(f"CRITICAL: Watchdog loop error for Race {race_no}: {e}")
            await asyncio.sleep(interval)

    def _update_prediction_odds(self, date_str: str, venue: str, race_no: int, win_odds: Dict):
        """Writes live odds into prediction files and recalculates Kelly stakes."""
        pred_dir = Config.BASE_DIR / "data" / "predictions"
        race_id = f"{date_str}_{venue}_R{race_no}"
        pred_file = pred_dir / f"prediction_{race_id}.json"

        # If no prediction for today, find the nearest future meeting date
        if not pred_file.exists():
            import glob
            pattern = str(pred_dir / f"prediction_*_{venue}_R{race_no}.json")
            candidates = sorted(glob.glob(pattern))
            future = [c for c in candidates if Path(c).stem.split("_")[1] >= date_str]
            if future:
                pred_file = Path(future[0])
                race_id = pred_file.stem.replace("prediction_", "")
            else:
                return

        try:
            with open(pred_file, "r", encoding="utf-8") as f:
                pred = json.load(f)

            # Update market_odds
            pred["market_odds"] = win_odds

            # Check for excessive odds movement (freeze betting if market moved too much)
            old_odds = pred.get("market_odds", {})
            if old_odds:
                for horse_no, new_odds in win_odds.items():
                    old = old_odds.get(horse_no)
                    if old and old > 0:
                        movement = abs(new_odds - old) / old
                        if movement > Config.MAX_ODDS_MOVEMENT:
                            logger.warning(f"Odds freeze: Horse {horse_no} moved {movement:.1%} (>{Config.MAX_ODDS_MOVEMENT:.0%})")
                            # Don't update stakes if market is too volatile
                            return
            
            # Recalculate Kelly stakes with safeguards
            probabilities = pred.get("probabilities", {})
            kelly_stakes = {}
            
            # Calculate edges for all horses first
            edges = {}
            for horse_no, prob in probabilities.items():
                # Apply confidence filter
                if prob < Config.MIN_CONFIDENCE:
                    continue
                    
                odds = win_odds.get(str(horse_no))
                if odds and odds > 1 and prob > 0:
                    edge = (prob * odds - 1) / (odds - 1)
                    edges[str(horse_no)] = edge
            
            # Sort by edge (highest first) and apply safeguards
            sorted_horses = sorted(edges.items(), key=lambda x: x[1], reverse=True)
            total_exposure = 0
            
            # Fetch rolling bankroll instead of static
            current_bankroll = self.bankroll_manager.get_current_bankroll()
            max_exposure = current_bankroll * 0.05  # 5% of bankroll max per race
            
            # Apply track-specific Kelly adjustment
            venue = race_id.split("_")[1] if "_" in race_id else "ST"
            track_multiplier = Config.TRACK_KELLY_MULTIPLIERS.get(venue, 1.0)
            adjusted_kelly = Config.KELLY_FRACTION * track_multiplier
            
            for horse_no, edge in sorted_horses:
                # Skip if edge is too small
                if edge < Config.MIN_EDGE:
                    continue
                
                # Skip if we already have 2 horses
                if len(kelly_stakes) >= 2:
                    continue
                
                # Calculate stake with track-adjusted Kelly
                stake = round(current_bankroll * adjusted_kelly * edge, 2)
                
                # Check exposure cap
                if total_exposure + stake > max_exposure:
                    remaining = max_exposure - total_exposure
                    if remaining > 0:
                        stake = round(remaining, 2)
                    else:
                        break
                
                # Round down to nearest $10 multiple (conservative)
                stake = max(10, int(stake // 10) * 10)
                
                kelly_stakes[horse_no] = stake
                total_exposure += stake

            pred["kelly_stakes"] = kelly_stakes
            pred["odds_updated_at"] = datetime.now().isoformat()

            # Save locally
            with open(pred_file, "w", encoding="utf-8") as f:
                json.dump(pred, f, indent=2)

            # Sync to Firestore
            try:
                self.firestore.upsert(Config.COL_PREDICTIONS, race_id, pred)
            except Exception as e:
                logger.error(f"Failed to sync prediction to Firestore: {e}")

            logger.info(f"📊 Updated odds for {race_id}: {len(win_odds)} horses, {len(kelly_stakes)} Kelly selections")
        except Exception as e:
            logger.error(f"Failed to update prediction odds for {race_id}: {e}")

if __name__ == "__main__":
    # Test script
    watchdog = MarketWatchdog(drop_threshold=0.1) # 10% for testing
    asyncio.run(watchdog.poll_and_detect(1, "ST"))
