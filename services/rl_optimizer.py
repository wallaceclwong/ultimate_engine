import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from loguru import logger

# Ensure project root is in path for services imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config
from services.betting_evaluator import BettingEvaluator

class RLOptimizer:
    """
    Reinforcement Learning style optimizer to adjust AI biases based on real-world performance.
    """
    def __init__(self):
        self.base_dir = Config.BASE_DIR
        self.bias_path = self.base_dir / "data/bias_correction.json"
        self.predictions_dir = self.base_dir / "data/predictions"
        self.results_dir = self.base_dir / "data/results"
        
        # Default biases if file missing
        self.defaults = {
            "synergy_weight_multiplier": 1.0,
            "sectional_weight_multiplier": 1.0,
            "confidence_bias": 0.0
        }
        self.bias_data = self.load_biases()

    def load_biases(self) -> Dict[str, Any]:
        if self.bias_path.exists():
            with open(self.bias_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"metadata": {}, "adjustments": self.defaults, "contextual": {}}

    def get_weights(self, date_str: str = None, venue: str = None) -> Dict[str, Any]:
        """
        Retrieves weights for a specific context (venue + month). 
        Falls back to global 'adjustments' if context not found.
        """
        if not date_str or not venue:
            return self.bias_data.get("adjustments", self.defaults)
        
        try:
            month = datetime.strptime(date_str, "%Y-%m-%d").month
            context_key = f"{venue}_M{month}"
            return self.bias_data.get("contextual", {}).get(context_key, self.bias_data.get("adjustments", self.defaults))
        except:
            return self.bias_data.get("adjustments", self.defaults)


    def save_biases(self, biases: Dict[str, Any]):
        biases["metadata"]["last_optimized"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(self.bias_path, "w", encoding="utf-8") as f:
            json.dump(biases, f, indent=2)
        logger.info(f"Updated biases saved to {self.bias_path}")

    def calculate_metrics_from_files(self, prediction_files: List[Path]) -> Dict[str, Any]:
        """
        Calculates ROI and Brier Score for a given list of prediction files.
        """
        import re
        total_stake = 0.0
        total_return = 0.0
        unit_stake = 10.0
        brier_scores = []

        for pred_file in prediction_files:
            try:
                with open(pred_file, "r", encoding="utf-8") as f:
                    pred = json.load(f)
                
                race_id = pred.get("race_id", "")
                rec_bet = pred.get("recommended_bet", "")
                probabilities = pred.get("probabilities", {})
                
                result_file = self.results_dir / f"results_{race_id}.json"
                if not result_file.exists():
                    continue

                with open(result_file, "r", encoding="utf-8") as f:
                    result = json.load(f)

                # 1. Brier Score Calculation (Calibration)
                # Formula: BS = 1/N * sum((f_i - o_i)^2)
                # where f_i is predicted prob, o_i is outcome (1 if win, 0 otherwise)
                actual_winner = ""
                for div in result.get("dividends", {}).get("WIN", []):
                    actual_winner = div.get("combination")
                    break # Usually only one winner in WIN pool
                
                if actual_winner and probabilities:
                    for selection, prob in probabilities.items():
                        outcome = 1.0 if selection == actual_winner else 0.0
                        brier_scores.append((prob - outcome) ** 2)

                # 2. ROI Calculation
                if not rec_bet or rec_bet in ("NO BET", ""):
                    continue

                # Determine stake (Kelly if available, otherwise unit)
                kelly_stakes = pred.get("kelly_stakes", {})
                numbers = re.findall(r'\d+', rec_bet)
                selection = numbers[0] if numbers else ""
                stake = kelly_stakes.get(selection, unit_stake) if selection else unit_stake
                if stake == 0:
                    continue

                # Calculate payout
                rec_bet_up = rec_bet.upper()
                bet_type = next((bt for bt in ["WIN", "PLACE", "QUINELLA"] if bt in rec_bet_up), None)
                if not bet_type:
                    continue

                dividends = result.get("dividends", {})
                payout = 0.0

                if bet_type in ["WIN", "PLACE"]:
                    pool = dividends.get(bet_type, [])
                    for div in pool:
                        if div.get("combination") == selection:
                            payout = (float(div["dividend"]) / 10.0) * stake
                            break
                elif bet_type == "QUINELLA" and len(numbers) >= 2:
                    sel_parts = sorted([numbers[0], numbers[1]])
                    for div in dividends.get("QUINELLA", []):
                        div_parts = sorted(div.get("combination", "").split(","))
                        if sel_parts == div_parts:
                            payout = (float(div["dividend"]) / 10.0) * stake
                            break

                total_stake += stake
                total_return += payout
            except Exception as e:
                logger.debug(f"Skipping {pred_file.name}: {e}")
                continue

        roi = ((total_return - total_stake) / total_stake * 100) if total_stake > 0 else 0.0
        avg_brier = sum(brier_scores) / len(brier_scores) if brier_scores else 0.0
        
        return {
            "roi": roi,
            "brier_score": avg_brier,
            "total_samples": len(prediction_files),
            "total_stake": total_stake,
            "total_return": total_return
        }

    def optimize_from_subset(self, prediction_files: List[Path]):
        """
        Groups prediction files by context (Venue_Month) and optimizes each separately.
        """
        # Group files by context
        groups = {}
        for f in prediction_files:
            try:
                parts = f.stem.split("_")
                date_str = parts[1]
                venue = parts[2]
                month = datetime.strptime(date_str, "%Y-%m-%d").month
                context_key = f"{venue}_M{month}"
                if context_key not in groups: groups[context_key] = []
                groups[context_key].append(f)
            except:
                continue
        
        if not groups:
            logger.warning("No valid contexts found in file set.")
            return

        biases = self.bias_data
        
        for context, files in groups.items():
            logger.info(f"Optimizing context: {context} ({len(files)} samples)")
            metrics = self.calculate_metrics_from_files(files)
            roi = metrics["roi"]
            brier = metrics["brier_score"]
            
            logger.info(f"  Result -> ROI: {roi:.1f}%, Brier: {brier:.4f}")

            # Fallback to current adjustments or defaults
            target_adj = biases.get("contextual", {}).get(context, biases.get("adjustments", self.defaults).copy())

            if roi < 0 or brier > 0.25:
                logger.info(f"  Suboptimal performance in {context}. Recalibrating...")
                if brier > 0.2:
                    target_adj["confidence_bias"] = round(min(0.6, target_adj.get("confidence_bias", 0) + 0.10), 2)
                if roi < 0:
                    target_adj["sectional_weight_multiplier"] = round(min(1.5, target_adj.get("sectional_weight_multiplier", 1.0) + 0.07), 2)
                    target_adj["synergy_weight_multiplier"] = round(max(0.6, target_adj.get("synergy_weight_multiplier", 1.0) - 0.07), 2)
            elif roi > 10:
                logger.info(f"  Strong performance in {context}. Reinforcing...")
                if brier < 0.15:
                    target_adj["confidence_bias"] = round(max(0.0, target_adj.get("confidence_bias", 0) - 0.02), 2)

            if "contextual" not in biases: biases["contextual"] = {}
            biases["contextual"][context] = target_adj

        # Final metadata update (global)
        global_metrics = self.calculate_metrics_from_files(prediction_files)
        biases["metadata"].update({
            "total_samples": global_metrics["total_samples"],
            "overall_accuracy": round(1.0 - global_metrics["brier_score"], 3),
            "avg_brier_score": round(global_metrics["brier_score"], 4)
        })
        self.save_biases(biases)



    def optimize_from_past_days(self, days: int = 7):
        """
        Analyzes performance over a range of past days and adjusts biases.
        Now uses a more robust glob for any files in the predictions directory.
        """
        prediction_files = list(self.predictions_dir.glob("prediction_*.json"))
        logger.debug(f"Total files in predictions dir: {len(prediction_files)}")
        
        # Optional: Filter by date if 'days' is provided
        if days and days > 0:
            from datetime import timedelta
            threshold_dt = datetime.now() - timedelta(days=days)
            logger.debug(f"Filtering files >= {threshold_dt.strftime('%Y-%m-%d')}")
            filtered = []
            for f in prediction_files:
                try:
                    # prediction_2024-09-08_ST_R1.json
                    parts = f.stem.split("_")
                    if len(parts) < 2: continue
                    date_str = parts[1]
                    f_dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if f_dt >= threshold_dt:
                        filtered.append(f)
                    else:
                        logger.trace(f"Skipping old file: {f.name}")
                except Exception as e:
                    logger.trace(f"Error parsing date from {f.name}: {e}")
                    pass
            prediction_files = filtered

        logger.info(f"Final file count for optimization: {len(prediction_files)}")
        if not prediction_files:
            logger.warning("No predictions found for the specified range.")
            return

        self.optimize_from_subset(prediction_files)



    def _calculate_recent_roi(self, days: int) -> float:
        # Legacy placeholder, now integrated into calculate_metrics_from_files
        metrics = self.calculate_metrics_from_files([]) # Dummy call
        return metrics["roi"]

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HKJC RL Optimizer")
    parser.add_argument("--days", type=int, default=7, help="Number of past days to analyze")
    args = parser.parse_args()

    optimizer = RLOptimizer()
    optimizer.optimize_from_past_days(days=args.days)

