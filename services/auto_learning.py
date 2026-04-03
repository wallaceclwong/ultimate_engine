"""
Post-Race Auto-Learning Module

Automatically triggers model recalibration after each race settles.
Analyzes prediction accuracy and adjusts model weights accordingly.
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from loguru import logger

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.settings import Config
from services.rl_optimizer import RLOptimizer


class AutoLearning:
    def __init__(self):
        self.optimizer = RLOptimizer()
        self.predictions_dir = Config.BASE_DIR / "data" / "predictions"
        self.results_dir = Config.BASE_DIR / "data" / "results"
        self.learning_log = Config.BASE_DIR / "data" / "logs" / "auto_learning.log"
        
    def trigger_post_race_learning(self, race_id: str):
        """
        Triggered after a race result is available.
        Evaluates prediction accuracy and updates model if needed.
        """
        # Try both date formats: 20260329 and 2026-03-29
        pred_file = self.predictions_dir / f"prediction_{race_id}.json"
        result_file = self.results_dir / f"results_{race_id}.json"
        
        # If not found, try with dash format
        if not pred_file.exists():
            # Convert 20260329_ST_R1 to 2026-03-29_ST_R1
            if "_" in race_id:
                parts = race_id.split("_")
                date_part = parts[0]
                if len(date_part) == 8 and date_part.isdigit():
                    formatted_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                    race_id_dash = f"{formatted_date}_{parts[1]}_{parts[2]}"
                    pred_file = self.predictions_dir / f"prediction_{race_id_dash}.json"
                    result_file = self.results_dir / f"results_{race_id_dash}.json"
        
        if not pred_file.exists() or not result_file.exists():
            logger.debug(f"Skipping auto-learning for {race_id}: missing files")
            return
        
        try:
            with open(pred_file, "r") as f:
                pred = json.load(f)
            with open(result_file, "r") as f:
                result = json.load(f)
            
            # Calculate prediction accuracy
            accuracy = self._calculate_accuracy(pred, result)
            
            # Log learning event
            self._log_learning_event(race_id, accuracy)
            
            # If accuracy is poor, trigger recalibration
            if accuracy["brier_score"] > 0.25 or accuracy["roi"] < -20:
                logger.warning(f"Poor performance on {race_id}: Brier={accuracy['brier_score']:.3f}, ROI={accuracy['roi']:.1f}%")
                self._trigger_recalibration(race_id)
            
            # If accuracy is excellent, log success
            elif accuracy["roi"] > 30:
                logger.info(f"Excellent performance on {race_id}: ROI={accuracy['roi']:.1f}%")
                
        except Exception as e:
            logger.error(f"Auto-learning failed for {race_id}: {e}")
    
    def _calculate_accuracy(self, pred: dict, result: dict) -> dict:
        """Calculate Brier score and ROI for a single race."""
        probs = pred.get("probabilities", {})
        kelly_stakes = pred.get("kelly_stakes", {})
        
        # Find winner
        winner = None
        for h in result.get("results", []):
            if h.get("plc") == "1":
                winner = str(h.get("horse_no"))
                break
        
        # Calculate Brier score
        brier = 0
        for horse_no, prob in probs.items():
            outcome = 1.0 if horse_no == winner else 0.0
            brier += (prob - outcome) ** 2
        brier = brier / len(probs) if probs else 1.0
        
        # Calculate ROI
        total_stake = sum(kelly_stakes.values())
        total_return = 0
        
        for horse_no, stake in kelly_stakes.items():
            if horse_no == winner:
                # Find dividend
                for div in result.get("dividends", {}).get("WIN", []):
                    if div.get("combination") == horse_no:
                        dividend = float(div.get("dividend", 0))
                        total_return += (dividend / 10.0) * stake
                        break
        
        roi = ((total_return - total_stake) / total_stake * 100) if total_stake > 0 else 0
        
        return {
            "brier_score": brier,
            "roi": roi,
            "stake": total_stake,
            "return": total_return
        }
    
    def _log_learning_event(self, race_id: str, accuracy: dict):
        """Log learning event to file."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "race_id": race_id,
            "brier_score": accuracy["brier_score"],
            "roi": accuracy["roi"],
            "stake": accuracy["stake"],
            "return": accuracy["return"]
        }
        
        # Append to log file
        self.learning_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.learning_log, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def _trigger_recalibration(self, race_id: str):
        """Trigger RL optimizer recalibration."""
        logger.info(f"Triggering recalibration based on {race_id} performance")
        
        # Run optimizer on recent predictions
        try:
            self.optimizer.optimize_from_past_days(days=7)
            logger.info("Recalibration complete")
        except Exception as e:
            logger.error(f"Recalibration failed: {e}")


def trigger_auto_learning_for_race(race_id: str):
    """Convenience function to trigger auto-learning for a specific race."""
    learner = AutoLearning()
    learner.trigger_post_race_learning(race_id)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        race_id = sys.argv[1]
        trigger_auto_learning_for_race(race_id)
    else:
        print("Usage: python auto_learning.py <race_id>")
        print("Example: python auto_learning.py 20260329_ST_R1")
