import os
import sys
from typing import Dict, Any, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config
from telegram_service import telegram_service

class NotificationService:
    def __init__(self):
        """
        GCP FCM deprecated in favor of Telegram Only architecture.
        TelegramService is already initialized with BOT_TOKEN and CHAT_ID.
        """
        pass

    async def send_race_briefing(
        self,
        race_id: str,
        race_no: int,
        distance: int,
        going: str,
        top_picks: list,          # [(horse_no, horse_name, prob, kelly_stake, odds), ...]
        confidence: float,
        recommended_bet: str,
        is_best_bet: bool,
        model_win_rate: float = 0.14,   # current empirical win rate (update as data grows)
    ):
        """
        Sends an honest per-race briefing to Telegram for EVERY race.
        Does NOT say 'BET' until we are in betting mode.
        """
        # ── Stale odds detection ──────────────────────────────────────────
        all_odds = [odds for (_, _, _, _, odds) in top_picks]
        stale_odds = all_odds and all(
            isinstance(o, (int, float)) and abs(o - 10.0) < 0.01 for o in all_odds if o
        )

        # ── Top pick probability ──────────────────────────────────────────
        top_prob = top_picks[0][2] if top_picks else 0.0

        # ── Honest verdict ────────────────────────────────────────────────
        # We are in TRACKING MODE — no BET label regardless of Kelly.
        # Verdict reflects signal quality only.
        if stale_odds:
            verdict = "⚠️ STALE ODDS — Kelly unreliable"
        elif top_prob < model_win_rate:
            # AI's top pick is below its own historical average — this is noise
            verdict = "📉 NOISE  (top pick below model avg)"
        elif confidence >= 0.55 and top_prob >= 0.18:
            verdict = "📡 STRONG SIGNAL  (track this)"
        elif confidence >= 0.40 or top_prob >= 0.14:
            verdict = "📶 SIGNAL  (weak edge)"
        else:
            verdict = "📊 TRACKING  (no clear edge)"

        # ── Build message ────────────────────────────────────────────────
        lines = [
            f"🏇 *{race_id}*  |  {distance}m  |  {going}",
            f"AI conf: {confidence:.0%}  |  {verdict}",
            "",
        ]

        for i, (h_no, h_name, prob, stake, odds) in enumerate(top_picks[:3]):
            medal = ["🥇", "🥈", "🥉"][i]
            odds_str  = f" @ {odds:.1f}" if isinstance(odds, (int, float)) and odds > 0 and not stale_odds else ""
            kelly_str = f"  Kelly HK${stake:.0f}" if stake >= 10 and not stale_odds else ""
            # Flag if pick is below model's historical average
            flag = " ⚠️" if prob < model_win_rate else ""
            lines.append(f"{medal} #{h_no} {h_name}  {prob:.1%}{odds_str}{kelly_str}{flag}")

        lines.append("")
        lines.append(f"📌 {recommended_bet}" if recommended_bet else "📌 No recommendation")

        # ── Honest context footer ─────────────────────────────────────────
        lines.append("")
        lines.append(f"_Model accuracy (57 races): WIN {model_win_rate:.0%} vs {model_win_rate/2:.0%} random_")
        lines.append(f"_Mode: TRACKING — not betting until accuracy improves_")

        msg = "\n".join(lines)
        try:
            await telegram_service.send_message(msg)
            print(f"[TELEGRAM] Race briefing sent for {race_id}")
        except Exception as e:
            print(f"[TELEGRAM] Failed to send race briefing: {e}")

    async def send_bet_alert(self, race_id: str, horse_name: str, confidence: float, ev: float):
        """
        Sends a high-priority Strategic Brief via Telegram.
        """
        reasoning = f"Statistical model identifies {horse_name} as a top-value play with {confidence*100:.1f}% confidence and {ev*100:.2f}x EV."
        
        # Consolidation Point: Re-routing all FCM logic to Telegram Elite Briefs
        try:
            success = await telegram_service.send_elite_brief(
                race_id=race_id,
                horse=horse_name,
                ev=ev,
                reasoning=reasoning
            )
            if success:
                print(f"[SUCCESS] Sent Telegram Elite Brief for {race_id}")
            return success
        except Exception as e:
            print(f"[ERROR] Failed to send Telegram notification: {e}")
            return False

# Singleton instance
notification_service = NotificationService()

if __name__ == "__main__":
    import asyncio
    # Test notification
    async def test():
        await notification_service.send_bet_alert("TEST_RACE", "WINNING_HORSE", 0.95, 1.25)
    
    asyncio.run(test())

