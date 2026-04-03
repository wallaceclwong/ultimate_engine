"""
Track Performance Analytics Module

Analyzes historical performance by track (ST vs HV) and other factors.
Provides data-driven recommendations for Kelly adjustments.
"""
import os
import sys
import json
from pathlib import Path
from collections import defaultdict
from loguru import logger

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.settings import Config


class TrackAnalytics:
    def __init__(self):
        self.predictions_dir = Config.BASE_DIR / "data" / "predictions"
        self.results_dir = Config.BASE_DIR / "data" / "results"
        
    def analyze_track_performance(self) -> dict:
        """
        Analyze ROI and win rate by track (ST vs HV).
        Returns recommendations for Kelly adjustments.
        """
        track_stats = defaultdict(lambda: {
            "races": 0,
            "wins": 0,
            "total_stake": 0,
            "total_return": 0,
            "brier_scores": []
        })
        
        # Scan all predictions and results
        for pred_file in self.predictions_dir.glob("prediction_*.json"):
            try:
                with open(pred_file, "r") as f:
                    pred = json.load(f)
                
                race_id = pred.get("race_id", "")
                if not race_id:
                    continue
                
                # Extract venue (ST or HV)
                parts = race_id.split("_")
                if len(parts) < 2:
                    continue
                venue = parts[1]
                
                # Find corresponding result
                result_file = self.results_dir / f"results_{race_id}.json"
                if not result_file.exists():
                    continue
                
                with open(result_file, "r") as f:
                    result = json.load(f)
                
                # Calculate metrics
                kelly_stakes = pred.get("kelly_stakes", {})
                probs = pred.get("probabilities", {})
                
                if not kelly_stakes:
                    continue
                
                # Find winner
                winner = None
                for h in result.get("results", []):
                    if h.get("plc") == "1":
                        winner = str(h.get("horse_no"))
                        break
                
                # Update stats
                track_stats[venue]["races"] += 1
                total_stake = sum(kelly_stakes.values())
                track_stats[venue]["total_stake"] += total_stake
                
                # Check if we won
                won = False
                for horse_no, stake in kelly_stakes.items():
                    if horse_no == winner:
                        won = True
                        # Find dividend
                        for div in result.get("dividends", {}).get("WIN", []):
                            if div.get("combination") == horse_no:
                                dividend = float(div.get("dividend", 0))
                                track_stats[venue]["total_return"] += (dividend / 10.0) * stake
                                break
                
                if won:
                    track_stats[venue]["wins"] += 1
                
                # Calculate Brier score
                if probs:
                    brier = 0
                    for horse_no, prob in probs.items():
                        outcome = 1.0 if horse_no == winner else 0.0
                        brier += (prob - outcome) ** 2
                    brier = brier / len(probs)
                    track_stats[venue]["brier_scores"].append(brier)
                
            except Exception as e:
                logger.debug(f"Skipping {pred_file.name}: {e}")
                continue
        
        # Calculate summary metrics
        summary = {}
        for venue, stats in track_stats.items():
            if stats["races"] == 0:
                continue
            
            win_rate = (stats["wins"] / stats["races"]) * 100
            roi = ((stats["total_return"] - stats["total_stake"]) / stats["total_stake"] * 100) if stats["total_stake"] > 0 else 0
            avg_brier = sum(stats["brier_scores"]) / len(stats["brier_scores"]) if stats["brier_scores"] else 0
            
            summary[venue] = {
                "races": stats["races"],
                "win_rate": win_rate,
                "roi": roi,
                "avg_brier": avg_brier,
                "total_stake": stats["total_stake"],
                "total_return": stats["total_return"]
            }
        
        return summary
    
    def get_kelly_recommendations(self) -> dict:
        """
        Based on track performance, recommend Kelly multipliers.
        """
        summary = self.analyze_track_performance()
        recommendations = {}
        
        for venue, stats in summary.items():
            # Default multiplier
            multiplier = 1.0
            
            # Adjust based on ROI
            if stats["roi"] > 15:
                multiplier = 1.1  # Increase Kelly for strong performance
            elif stats["roi"] > 10:
                multiplier = 1.0  # Keep baseline
            elif stats["roi"] > 0:
                multiplier = 0.9  # Slight reduction
            else:
                multiplier = 0.8  # Reduce for negative ROI
            
            # Further adjust based on Brier score (calibration)
            if stats["avg_brier"] > 0.25:
                multiplier *= 0.9  # Model is poorly calibrated
            
            recommendations[venue] = {
                "multiplier": round(multiplier, 2),
                "reason": f"ROI={stats['roi']:.1f}%, Brier={stats['avg_brier']:.3f}, WinRate={stats['win_rate']:.1f}%"
            }
        
        return recommendations
    
    def print_report(self):
        """Print a formatted performance report."""
        summary = self.analyze_track_performance()
        recommendations = self.get_kelly_recommendations()
        
        print("\n" + "="*60)
        print("TRACK PERFORMANCE ANALYTICS")
        print("="*60)
        
        for venue, stats in summary.items():
            print(f"\n{venue} (Sha Tin)" if venue == "ST" else f"\n{venue} (Happy Valley)")
            print(f"  Races:      {stats['races']}")
            print(f"  Win Rate:   {stats['win_rate']:.1f}%")
            print(f"  ROI:        {stats['roi']:+.1f}%")
            print(f"  Brier:      {stats['avg_brier']:.3f}")
            print(f"  Stake:      ${stats['total_stake']:,.2f}")
            print(f"  Return:     ${stats['total_return']:,.2f}")
            
            if venue in recommendations:
                rec = recommendations[venue]
                print(f"  Recommended Kelly Multiplier: {rec['multiplier']}")
                print(f"  Reason: {rec['reason']}")
        
        print("\n" + "="*60)


if __name__ == "__main__":
    analytics = TrackAnalytics()
    analytics.print_report()
