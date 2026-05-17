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
        
        # 2. Check if movement qualifies for a 'War Room' audit (>3% shortening)
        # RELIEF ADJUSTMENT: Lowered from 5% to 3% to increase frequency
        if movement.movement_pct > -0.03:
            logger.info(f"Movement ({movement.movement_pct:+.1%}) below relief threshold (3%) for audit.")
            return None
            
        logger.info(f"🔥 SMART MONEY ALERT: {horse_no} shortened {movement.movement_pct:+.1%}. Triggering DeepSeek-R1...")
        
        # 3. Prepare data for ConsensusAgent
        race_data = self._load_race_data(date_str, venue, race_no)
        if race_data is None:
            logger.error("Could not load race data for audit.")
            return None
            
        # 4. Run the DeepSeek-R1 Audit
        market_context = {
            'movement': movement.movement_pct,
            'trend': movement.trend
        }
        
        consensus_agent.reload_pedigree()
        verdict, reasoning = await consensus_agent.get_consensus(race_data, horse_no, market_context)
        
        # 5. Append to central log
        try:
            log_path = Path(__file__).parent.parent / "final_predictions.log"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n[LIVE AUDIT] {date_str} {venue} R{race_no} | Horse #{horse_no}\n")
                f.write(f"Movement: {movement.initial_odds} -> {movement.current_odds} ({movement.movement_pct:+.1%})\n")
                f.write(f"Verdict: {verdict}\n")
                f.write(f"Brief: {reasoning}\n")
                f.write("-" * 60 + "\n")
        except Exception as e:
            logger.error(f"Failed to append live brief to log: {e}")

        # 6. Filtering — log smart money signals locally only.
        # War Room Verdict (fired by ultimate_scheduler_vm.py at T-15) is the ONLY Telegram alert.
        is_elite = "Grade [S]" in reasoning or "Grade [A]" in reasoning
        is_moderate = "Grade [B]" in reasoning
        is_speculative = "Grade [C]" in reasoning

        if (is_elite or is_moderate or is_speculative) and verdict in ["CONFIRMED", "CAUTION"]:
            if is_elite:
                label = "HIGH CONVICTION"
            elif is_moderate:
                label = "MODERATE CONVICTION"
            else:
                label = "SPECULATIVE SIGNAL"
            logger.info(
                f"[SMART MONEY {label}] {race_id} #{horse_no}: {verdict} | "
                f"Move: {movement.initial_odds} → {movement.current_odds} ({movement.movement_pct:+.1%})"
            )
        else:
            logger.info(f"[LIVE AUDIT] Filtered (Grade/Verdict below threshold): {verdict}")
            
        return verdict, reasoning

    def _load_race_data(self, date_str, venue, race_no):
        """Loads the horse data for the race from prediction cache using absolute paths."""
        try:
            # Use absolute path to avoid CWD issues
            base_data_dir = Path(__file__).parent.parent.absolute() / "data" / "processed"
            
            # Try multiple date formats and naming conventions
            date_compact = date_str.replace("-", "")
            possible_files = [
                f"features_{date_str}_{venue}_R{race_no}.parquet",
                f"features_{date_compact}_{venue}_R{race_no}.parquet",
                f"features_{date_compact}_{venue}_R{race_no:02d}.parquet",
            ]
            
            for filename in possible_files:
                path = base_data_dir / filename
                if path.exists():
                    logger.info(f"  [OK] Loading race data from: {path.name}")
                    return pd.read_parquet(path)
            
            logger.error(f"Processed features file not found in {base_data_dir}. Tried: {possible_files}")
            return None
        except Exception as e:
            logger.error(f"Error loading race data: {e}")
            return None

live_audit_service = LiveAuditService()
