import asyncio
from loguru import logger
from services.live_odds_monitor import get_live_odds_monitor
from consensus_agent import consensus_agent
from services.notification_service import NotificationService
from telegram_service import telegram_service
import pandas as pd
from pathlib import Path

class LiveAuditService:
    """
    Orchestrates the 'Dynamic War Room' by connecting live odds monitoring
    with DeepSeek-R1 reasoning.
    """
    def __init__(self):
        self.monitor = get_live_odds_monitor()
        self.notification = NotificationService()
        
    async def audit_late_money(self, race_id: str, horse_no: str, date_str: str, venue: str, race_no: int):
        """
        Performs a T-15 minute audit if significant market movement is detected.
        """
        logger.info(f"[LIVE AUDIT] Analyzing {race_id} Horse #{horse_no} for Smart Money...")
        
        # 1. Update odds state and get movement
        state = self.monitor.update_race_state(date_str, venue, race_no)
        if not state or horse_no not in state.movements:
            logger.warning(f"No odds movement found for {race_id} Horse #{horse_no}")
            return None
            
        movement = state.movements[horse_no]
        
        # 2. Check if movement qualifies for a 'War Room' audit (>15% shortening)
        if movement.movement_pct > -0.15:
            logger.info(f"Movement ({movement.movement_pct:+.1%}) below threshold for audit.")
            return None
            
        logger.info(f"🔥 SMART MONEY ALERT: {horse_no} shortened {movement.movement_pct:+.1%}. Triggering DeepSeek-R1...")
        
        # 3. Prepare data for ConsensusAgent (We need the full race_data)
        # For simplicity in this service, we assume race_data is passed or loaded
        # Here we mock the load - in production, this would come from the prediction results
        race_data = self._load_race_data(date_str, venue, race_no)
        if race_data is None:
            logger.error("Could not load race data for audit.")
            return None
            
        # 4. Run the DeepSeek-R1 Audit
        market_context = {
            'movement': movement.movement_pct,
            'trend': movement.trend
        }
        
        verdict, reasoning = await consensus_agent.get_consensus(race_data, horse_no, market_context)
        
        # 5. Filtering: ONLY notify for high-conviction S/A grades
        is_high_conviction = "Grade [S]" in reasoning or "Grade [A]" in reasoning
        
        if is_high_conviction and verdict == "CONFIRMED":
            logger.info(f"🏆 HIGH CONVICTION SIGNAL: {verdict} - {reasoning}")
            
            # Send Telegram Alert
            header = f"🚨 *LIVE SMART MONEY ALERT: {race_id}*"
            body = (
                f"\n🎯 *Target:* Horse #{horse_no}"
                f"\n📉 *Odds:* {movement.initial_odds} → {movement.current_odds} ({movement.movement_pct:+.1%})"
                f"\n\n🧠 *Lunar Leap Verdict:* {verdict}\n{reasoning}"
            )
            await telegram_service.send_message(f"{header}\n{body}")
        else:
            logger.info(f"Audit complete but filtered (Grade/Verdict too low): {verdict} - {reasoning}")
            
        return verdict, reasoning

    def _load_race_data(self, date_str, venue, race_no):
        """Loads the horse data for the race from prediciton cache."""
        # Implementation depends on where predict_today.py saves its intermediate results
        # Usually it's in data/feature_matrix_*.parquet or a similar cache
        # For this audit, we need the win_odds and fair_odds.
        try:
            # Mock loading - in reality, we'd fetch the DF used by predict_today.py
            # For now, we'll return a minimal DF that get_consensus can use
            # This would be fleshed out to use the actual feature matrix
            return None 
        except:
            return None

live_audit_service = LiveAuditService()
