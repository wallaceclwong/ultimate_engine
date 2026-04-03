import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from dataclasses import dataclass

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config

@dataclass
class MarketAlert:
    horse_no: str
    severity: str  # "HIGH", "MEDIUM", "LOW"
    type: str      # "LATE_PLUNGE", "DIVERGENCE", "STEADY_DROP"
    description: str
    odds_move: str
    implied_prob_change: float

class SmartMoneyDetector:
    """
    Analyzes sequences of odds snapshots to detect "Smart Money" market moves.
    Uses the SAME market_alerts_{race_id}.json filename as MarketWatchdog,
    merging results so the dashboard always reads one unified file.
    """
    def __init__(self):
        self.odds_dir = Path("data/odds")
        self.predictions_dir = Path("data/predictions")
        self.alerts_dir = Path("data/alerts")
        self.alerts_dir.mkdir(parents=True, exist_ok=True)

    def get_snapshots(self, date_str: str, race_no: int) -> List[Dict[str, Any]]:
        """Finds and sorts all snapshots for a specific race and date."""
        date_compact = date_str.replace("-", "")
        # Try exact date formats first, fall back to any snapshot for that race
        for pattern in [
            f"snapshot_{date_str}_R{race_no}_*.json",
            f"snapshot_{date_compact}_R{race_no}_*.json",
        ]:
            files = list(self.odds_dir.glob(pattern))
            if files:
                break

        snapshots = []
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as f_in:
                    snapshots.append(json.load(f_in))
            except Exception:
                continue
        return sorted(snapshots, key=lambda x: x.get("timestamp", ""))

    def detect_moves(self, date_str: str, venue: str, race_no: int) -> List[MarketAlert]:
        """
        Compares consecutive odds snapshots for plunges and AI-divergence signals.
        """
        snapshots = self.get_snapshots(date_str, race_no)
        if len(snapshots) < 2:
            return []

        latest = snapshots[-1]
        previous = snapshots[-2]

        prediction = self._load_prediction(date_str, venue, race_no)
        ai_probs = prediction.get("probabilities", {}) if prediction else {}

        alerts = []

        for horse_no, current_odds in latest.get("win_odds", {}).items():
            prev_odds = previous.get("win_odds", {}).get(horse_no)
            if not prev_odds or current_odds <= 0:
                continue

            current_prob = 1.0 / current_odds
            prev_prob = 1.0 / prev_odds
            prob_change = current_prob - prev_prob

            # 1. Late Plunge (odds shortening = prob increasing)
            if prob_change > 0.05:
                severity = "HIGH" if prob_change > 0.10 else "MEDIUM"
                alerts.append(MarketAlert(
                    horse_no=horse_no,
                    severity=severity,
                    type="LATE_PLUNGE",
                    description=f"Sharp odds drop: {prev_odds} -> {current_odds}",
                    odds_move=f"{prev_odds} -> {current_odds}",
                    implied_prob_change=round(prob_change * 100, 1)
                ))

            # 2. AI Divergence — AI liked it AND market is now following
            ai_prob = ai_probs.get(horse_no, 0)
            if ai_prob > 0.25 and prob_change > 0:
                alerts.append(MarketAlert(
                    horse_no=horse_no,
                    severity="MEDIUM",
                    type="DIVERGENCE",
                    description=f"Smart money following AI pick. AI Prob: {ai_prob:.0%}",
                    odds_move=f"{prev_odds} -> {current_odds}",
                    implied_prob_change=round(prob_change * 100, 1)
                ))

        self._save_alerts(date_str, venue, race_no, alerts)
        return alerts

    def _load_prediction(self, date_str: str, venue: str, race_no: int) -> Dict[str, Any]:
        p_path = self.predictions_dir / f"prediction_{date_str}_{venue}_R{race_no}.json"
        if p_path.exists():
            with open(p_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_alerts(self, date_str: str, venue: str, race_no: int, alerts: List[MarketAlert]):
        race_id = f"{date_str}_{venue}_R{race_no}"
        # UNIFIED filename — same as MarketWatchdog._save_alerts()
        filename = self.alerts_dir / f"market_alerts_{race_id}.json"

        # Merge with any existing watchdog alerts (preserves watchdog's live data)
        existing_alerts = []
        if filename.exists():
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    existing_alerts = json.load(f).get("alerts", [])
            except:
                pass

        new_dicts = [
            {
                "horse_no": a.horse_no,
                "severity": a.severity,
                "type": a.type,
                "description": a.description,
                "odds_move": a.odds_move,
                "implied_prob_change": a.implied_prob_change,
                "source": "SmartMoneyDetector",
                "timestamp": datetime.now().isoformat()
            } for a in alerts
        ]

        # Deduplicate by horse_no+type, keep latest
        all_alerts = existing_alerts + new_dicts
        deduped = {}
        for a in all_alerts:
            key = f"{a.get('horse_no')}_{a.get('type', '')}"
            deduped[key] = a

        with open(filename, "w", encoding="utf-8") as f:
            json.dump({
                "race_id": race_id,
                "updated_at": datetime.now().isoformat(),
                "alerts": list(deduped.values())
            }, f, indent=2)

    def run_all(self, date_str: str, venue: str, num_races: int = 9):
        """Run detection across all races for a meeting."""
        total = 0
        for r in range(1, num_races + 1):
            a = self.detect_moves(date_str, venue, r)
            if a:
                print(f"R{r}: {len(a)} alert(s) — {[x.type for x in a]}")
            total += len(a)
        print(f"Total alerts: {total}")
        return total

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HKJC Smart Money Detector")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--venue", type=str, default="HV")
    parser.add_argument("--race", type=int, default=None)
    parser.add_argument("--races", type=int, default=9)
    args = parser.parse_args()

    detector = SmartMoneyDetector()
    if args.race:
        alerts = detector.detect_moves(args.date, args.venue, args.race)
        print(f"R{args.race}: {len(alerts)} alert(s)")
    else:
        detector.run_all(args.date, args.venue, args.races)
