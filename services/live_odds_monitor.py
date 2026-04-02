"""
Live Odds Monitor Service
Monitors odds movements in real-time and adjusts predictions
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger
import asyncio
from collections import defaultdict

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config

@dataclass
class OddsMovement:
    """Tracks odds movement for a horse"""
    horse_no: str
    initial_odds: float
    current_odds: float
    movement_pct: float
    trend: str  # 'drift', 'shorten', 'stable', 'late_money'
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RaceOddsState:
    """Current odds state for a race"""
    race_id: str
    venue: str
    race_no: int
    timestamp: datetime
    win_odds: Dict[str, float]
    place_odds: Dict[str, float]
    movements: Dict[str, OddsMovement] = field(default_factory=dict)
    market_confidence: float = 0.5
    late_money_horses: List[str] = field(default_factory=list)

class LiveOddsMonitor:
    """
    Monitors live odds and provides real-time adjustments.
    
    Features:
    - Tracks odds movements over time
    - Identifies late money (significant shortening)
    - Calculates market confidence
    - Provides probability adjustments
    """
    
    def __init__(self, odds_dir: Path = None):
        self.odds_dir = odds_dir or Path("data/odds")
        self.race_states: Dict[str, RaceOddsState] = {}
        
        # Thresholds
        self.significant_movement = 0.10  # 10% change
        self.late_money_threshold = 0.15  # 15% shortening
        self.max_confidence_boost = 0.15  # Max 15% boost from odds
        
        # Tracking
        self.last_check = datetime.now()
        self.check_interval = 30  # seconds
        
        logger.info("Live Odds Monitor initialized")
    
    def load_latest_odds(self, date_str: str, venue: str, race_no: int) -> Optional[RaceOddsState]:
        """Load the most recent odds snapshot for a race"""
        pattern = f"snapshot_{date_str.replace('-', '')}_R{race_no}_*.json"
        files = sorted(self.odds_dir.glob(pattern), key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not files:
            return None
        
        try:
            with open(files[0], 'r') as f:
                data = json.load(f)
            
            race_id = f"{date_str}_{venue}_R{race_no}"
            
            return RaceOddsState(
                race_id=race_id,
                venue=data.get('venue', venue),
                race_no=data.get('race_no', race_no),
                timestamp=datetime.fromtimestamp(files[0].stat().st_mtime),
                win_odds=data.get('win_odds', {}),
                place_odds=data.get('place_odds', {})
            )
        except Exception as e:
            logger.error(f"Error loading odds: {e}")
            return None
    
    def calculate_movements(self, current: RaceOddsState, baseline: RaceOddsState) -> Dict[str, OddsMovement]:
        """Calculate odds movements from baseline to current"""
        movements = {}
        
        for horse_no, current_odds in current.win_odds.items():
            baseline_odds = baseline.win_odds.get(horse_no, current_odds)
            
            if baseline_odds > 0:
                movement_pct = (current_odds - baseline_odds) / baseline_odds
                
                # Determine trend
                if movement_pct > self.significant_movement:
                    trend = 'drift'
                elif movement_pct < -self.late_money_threshold:
                    trend = 'late_money'
                elif movement_pct < -self.significant_movement:
                    trend = 'shorten'
                else:
                    trend = 'stable'
                
                movements[horse_no] = OddsMovement(
                    horse_no=horse_no,
                    initial_odds=baseline_odds,
                    current_odds=current_odds,
                    movement_pct=movement_pct,
                    trend=trend
                )
        
        return movements
    
    def update_race_state(self, date_str: str, venue: str, race_no: int) -> Optional[RaceOddsState]:
        """Update odds state for a race and calculate movements"""
        race_id = f"{date_str}_{venue}_R{race_no}"
        
        # Load latest odds
        current = self.load_latest_odds(date_str, venue, race_no)
        if not current:
            return None
        
        # Check if we have a previous state
        if race_id in self.race_states:
            previous = self.race_states[race_id]
            
            # Calculate movements from previous state
            current.movements = self.calculate_movements(current, previous)
            
            # Identify late money horses
            current.late_money_horses = [
                h for h, m in current.movements.items() 
                if m.trend == 'late_money'
            ]
            
            # Calculate market confidence
            stable_count = sum(1 for m in current.movements.values() if m.trend == 'stable')
            total = len(current.movements)
            current.market_confidence = stable_count / total if total > 0 else 0.5
        else:
            # First load - no movements yet
            current.market_confidence = 0.5
        
        # Store state
        self.race_states[race_id] = current
        
        return current
    
    def get_odds_adjustment(self, horse_no: str, race_id: str) -> float:
        """
        Get probability adjustment factor based on odds movement.
        
        Returns:
            Adjustment factor (1.0 = no change, <1.0 = reduce confidence, >1.0 = boost)
        """
        if race_id not in self.race_states:
            return 1.0
        
        state = self.race_states[race_id]
        
        if horse_no not in state.movements:
            return 1.0
        
        movement = state.movements[horse_no]
        
        # Late money = boost probability (smart money knows something)
        if movement.trend == 'late_money':
            return 1.0 + min(abs(movement.movement_pct), self.max_confidence_boost)
        
        # Significant drift = reduce probability (market losing confidence)
        if movement.trend == 'drift':
            return 1.0 - min(movement.movement_pct, self.max_confidence_boost)
        
        # Shortening but not late money = slight boost
        if movement.trend == 'shorten':
            return 1.0 + min(abs(movement.movement_pct) * 0.5, 0.05)
        
        # Stable = no change
        return 1.0
    
    def adjust_probabilities(self, probabilities: Dict[str, float], race_id: str) -> Dict[str, float]:
        """Adjust probabilities based on live odds movements"""
        if race_id not in self.race_states:
            logger.debug(f"No odds data for {race_id}, skipping adjustment")
            return probabilities
        
        state = self.race_states[race_id]
        adjusted = {}
        
        logger.info(f"[LIVE ODDS] Adjusting probabilities for {race_id}")
        logger.info(f"  Market confidence: {state.market_confidence:.1%}")
        logger.info(f"  Late money horses: {state.late_money_horses}")
        
        for horse_no, prob in probabilities.items():
            adjustment = self.get_odds_adjustment(horse_no, race_id)
            adjusted_prob = prob * adjustment
            adjusted[horse_no] = adjusted_prob
            
            if adjustment != 1.0:
                change_pct = (adjustment - 1.0) * 100
                logger.info(f"  Horse #{horse_no}: {prob:.1%} → {adjusted_prob:.1%} ({change_pct:+.1f}%)")
        
        # Renormalize to sum to 1.0
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {h: p / total for h, p in adjusted.items()}
        
        return adjusted
    
    def get_betting_recommendation(self, race_id: str, horse_no: str) -> Dict:
        """Get betting recommendation based on odds analysis"""
        if race_id not in self.race_states:
            return {'recommendation': 'NO DATA', 'confidence': 0.5}
        
        state = self.race_states[race_id]
        
        if horse_no not in state.movements:
            return {'recommendation': 'NO MOVEMENT', 'confidence': 0.5}
        
        movement = state.movements[horse_no]
        
        recommendations = {
            'late_money': {'rec': 'STRONG BUY', 'confidence': 0.85, 'reason': 'Late money detected'},
            'shorten': {'rec': 'BUY', 'confidence': 0.75, 'reason': 'Odds shortening'},
            'stable': {'rec': 'HOLD', 'confidence': 0.6, 'reason': 'Stable odds'},
            'drift': {'rec': 'AVOID', 'confidence': 0.4, 'reason': 'Odds drifting'}
        }
        
        return recommendations.get(movement.trend, {'rec': 'UNKNOWN', 'confidence': 0.5, 'reason': 'No pattern'})
    
    async def monitor_race(self, date_str: str, venue: str, race_no: int, duration_minutes: int = 30):
        """Monitor a race for a specified duration"""
        race_id = f"{date_str}_{venue}_R{race_no}"
        logger.info(f"Starting live odds monitoring for {race_id}")
        
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        check_count = 0
        
        while datetime.now() < end_time:
            try:
                state = self.update_race_state(date_str, venue, race_no)
                check_count += 1
                
                if state:
                    logger.info(f"[CHECK {check_count}] {race_id} - Confidence: {state.market_confidence:.1%}")
                    
                    # Log significant movements
                    for horse_no, movement in state.movements.items():
                        if movement.trend != 'stable':
                            logger.info(f"  Horse #{horse_no}: {movement.trend} ({movement.movement_pct:+.1%})")
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error monitoring {race_id}: {e}")
                await asyncio.sleep(60)  # Wait longer on error
        
        logger.info(f"Monitoring complete for {race_id} ({check_count} checks)")

# Singleton instance
_live_odds_monitor = None

def get_live_odds_monitor() -> LiveOddsMonitor:
    """Get the global live odds monitor instance"""
    global _live_odds_monitor
    if _live_odds_monitor is None:
        _live_odds_monitor = LiveOddsMonitor()
    return _live_odds_monitor

# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Live Odds Monitor")
    parser.add_argument("--date", required=True, help="Date (YYYY-MM-DD)")
    parser.add_argument("--venue", required=True, help="Venue (ST or HV)")
    parser.add_argument("--race", type=int, required=True, help="Race number")
    parser.add_argument("--duration", type=int, default=30, help="Monitor duration in minutes")
    
    args = parser.parse_args()
    
    async def main():
        monitor = get_live_odds_monitor()
        await monitor.monitor_race(args.date, args.venue, args.race, args.duration)
    
    asyncio.run(main())
