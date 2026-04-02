import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
from models.schemas import Bet, Betslip, Prediction, RaceResult
from config.settings import Config
from services.firestore_service import FirestoreService

class BetslipService:
    def __init__(self):
        self.base_dir = Path("data/betslips")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.firestore = FirestoreService()

    def stage_bets(self, predictions: List[Prediction]) -> Betslip:
        """Converts predictions into a staged betslip."""
        bets = []
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        for pred in predictions:
            # Extract selection from recommended_bet (e.g., "WIN 5")
            import re
            parts = pred.recommended_bet.split(" ")
            if len(parts) < 2: continue
            
            bet_type = parts[0]
            selection = parts[1]
            
            # Use Kelly stake for this selection
            stake = pred.kelly_stakes.get(selection, 0.0)
            
            if stake > 0:
                bet = Bet(
                    bet_id=f"bet_{pred.race_id}_{selection}",
                    race_id=pred.race_id,
                    selection=selection,
                    bet_type=bet_type,
                    stake=stake,
                    odds_at_staging=0.0, # Will be filled by execution engine if available
                    status="STAGED"
                )
                bets.append(bet)
        
        # Use timestamp to avoid collision if run multiple times per day
        timestamp = datetime.now().strftime("%H%M%S")
        betslip = Betslip(
            slip_id=f"slip_{date_str}_{timestamp}",
            date=datetime.now(),
            bets=bets,
            total_stake=sum(b.stake for b in bets),
            status="OPEN"
        )
        
        self.save_betslip(betslip)
        return betslip

    def save_betslip(self, betslip: Betslip):
        """Saves betslip to local JSON and Firestore."""
        date_str = betslip.date.strftime("%Y-%m-%d")
        # Use slip_id in filename to avoid overwrites
        filename = self.base_dir / f"betslip_{betslip.slip_id}.json"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(betslip.model_dump_json(indent=2))
        
        # Cloud Sync
        self.firestore.upsert(Config.COL_BETSLIPS, betslip.slip_id, betslip)
        print(f"[BETSLIP] Saved {betslip.slip_id} to local and cloud.")

    def load_betslip(self, date_str: str) -> Optional[Betslip]:
        """Loads betslip for a specific date."""
        filename = self.base_dir / f"betslip_{date_str}.json"
        if filename.exists():
            with open(filename, "r", encoding="utf-8") as f:
                return Betslip.model_validate_json(f.read())
        return None

    def settle_betslip(self, date_str: str, results: Dict[str, RaceResult]):
        """Settles all bets in a slip based on race results."""
        betslip = self.load_betslip(date_str)
        if not betslip: return

        total_return = 0.0
        for bet in betslip.bets:
            result = results.get(bet.race_id)
            if not result: continue

            # Simplified settlement logic (matches BettingEvaluator)
            # This would be expanded for more complex bet types
            is_win = False
            payout = 0.0
            
            if bet.bet_type == "WIN" and bet.selection in result.winners:
                is_win = True
                payout = (result.win_dividend / 10.0) * bet.stake
            elif bet.bet_type == "PLACE" and bet.selection in result.placings:
                is_win = True
                # Index matching for place dividends would be needed here
                # For now, placeholder indexing:
                idx = result.placings.index(bet.selection)
                if idx < len(result.place_dividends):
                    payout = (result.place_dividends[idx] / 10.0) * bet.stake

            bet.status = "WIN" if is_win else "LOSS"
            bet.payout = payout
            total_return += payout

        betslip.total_return = total_return
        betslip.status = "SETTLED"
        self.save_betslip(betslip)
        print(f"[BETSLIP] Settled {betslip.slip_id}. Total Return: ${total_return:.2f}")

if __name__ == "__main__":
    # Quick Test
    service = BetslipService()
    # Mock some data if needed for verification
