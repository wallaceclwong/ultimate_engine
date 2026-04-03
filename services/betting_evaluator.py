import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config
from services.bigquery_service import BigQueryService

class BettingEvaluator:
    def __init__(self):
        self.results_dir = Path("data/results")
        self.predictions_dir = Path("data/predictions")
        self.unit_stake = 10.0  # Default $10 unit stake for calculations
        self.bigquery = BigQueryService()

    def evaluate_day(self, date_str: str, venue: str) -> List[Dict]:
        """Evaluates all predictions for a specific race day and returns structured data."""
        results_list = []
        
        # Look for prediction files for this date
        pattern = f"prediction_{date_str}_{venue}_R*.json"
        prediction_files = sorted(list(self.predictions_dir.glob(pattern)), key=lambda x: int(x.stem.split('_R')[-1]))

        if not prediction_files:
            return []

        for pred_file in prediction_files:
            try:
                with open(pred_file, "r", encoding="utf-8") as f:
                    pred_data = json.load(f)
                
                race_id = pred_data["race_id"]
                race_no = race_id.split("_R")[-1]
                rec_bet = pred_data.get("recommended_bet", "")
                
                if not rec_bet or rec_bet == "NO BET":
                    continue

                # Load results
                result_file = self.results_dir / f"results_{race_id}.json"
                if not result_file.exists():
                    continue

                with open(result_file, "r", encoding="utf-8") as f:
                    result_data = json.load(f)

                # Use Kelly stake if available, otherwise unit stake
                kelly_stakes = pred_data.get("kelly_stakes", {})
                
                import re
                numbers = re.findall(r'\d+', rec_bet)
                selection = numbers[0] if numbers else ""
                
                # Use 0.0 as default if Kelly didn't bet
                stake = kelly_stakes.get(selection, 0.0)
                
                ai_roi = 0.0
                profit_dividend = self.calculate_profit(rec_bet, result_data)
                ai_p_l = profit_dividend - 10.0 if profit_dividend > 0 else -10.0
                ai_roi = (ai_p_l / 10.0) * 100
                
                # 2. Kelly ROI (Actual stake)
                status = "WIN" if profit_dividend > 0 else "LOSS"
                status_icon = "✅" if status == "WIN" else "❌"
                
                # Normalized profit for Kelly
                gross_payout = (profit_dividend / 10.0) * stake if (status == "WIN" and stake > 0) else 0.0
                p_l = gross_payout - stake
                kelly_roi = (p_l / stake * 100) if stake > 0 else 0.0

                # Extract official winner
                official_win = next((h["horse_no"] for h in result_data.get("results", []) if h.get("plc") == "1"), "")
                
                results_list.append({
                    "race_no": race_no,
                    "race_id": race_id,
                    "official_result": f"WIN {official_win}" if official_win else "--",
                    "result_status": f"{status_icon} {status}",
                    "ai_top_pick": rec_bet,
                    "kelly_stake": stake,
                    "p_l": round(p_l, 2),
                    "ai_roi": round(ai_roi, 1),
                    "kelly_roi": round(kelly_roi, 1)
                })

            except Exception as e:
                print(f"Error evaluating {pred_file.name}: {e}")

        return results_list

    def format_markdown_report(self, date_str: str, venue: str, results_list: List[Dict]) -> str:
        """Formats the results list into a pretty Markdown table with enhanced metrics."""
        if not results_list:
            return "### 📭 No data available\nNo valid results found for this meeting."
            
        total_stake = sum(r['kelly_stake'] for r in results_list)
        total_p_l = sum(r['p_l'] for r in results_list)
        total_return = total_stake + total_p_l
        overall_kelly_roi = (total_p_l / total_stake * 100) if total_stake > 0 else 0
        
        # AI Fixed ROI (Assuming $10 unit bet on every race)
        total_ai_stake = len(results_list) * 10.0
        # Re-calculate AI P&L to get accurate total
        total_ai_p_l = sum((r['ai_roi'] / 100.0) * 10.0 for r in results_list)
        overall_ai_roi = (total_ai_p_l / total_ai_stake * 100) if total_ai_stake > 0 else 0

        wins = sum(1 for r in results_list if "WIN" in r['result_status'])
        win_rate = (wins / len(results_list) * 100) if results_list else 0
        
        # Color the net profit
        p_l_color = "🟢" if total_p_l >= 0 else "🔴"
        
        report = f"# 📊 Performance Report: {date_str} ({venue})\n\n"
        
        report += "## 📈 Summary Metrics\n"
        report += f"| Metric | Value |\n"
        report += f"| :--- | :--- |\n"
        report += f"| **Total Races** | {len(results_list)} |\n"
        report += f"| **Win Rate** | {win_rate:.1f}% ({wins}/{len(results_list)}) |\n"
        report += f"| **Total Kelly Stake** | ${total_stake:,.2f} |\n"
        report += f"| **Net Profit (Kelly)** | {p_l_color} **${total_p_l:,.2f}** |\n"
        report += f"| **Overall AI ROI** | **{overall_ai_roi:.1f}%** |\n"
        report += f"| **Overall Kelly ROI**| **{overall_kelly_roi:.1f}%** |\n\n"
        
        report += "## 🏁 Detailed Results Breakdown\n\n"
        report += "| Race No | Official Result | AI Pick | Kelly Stake | Kelly Result | ROI (AI) | ROI (Kelly) |\n"
        report += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        
        for r in results_list:
            k_stake = f"**${r['kelly_stake']:,.2f}**" if r['kelly_stake'] > 10 else f"${r['kelly_stake']:,.2f}"
            p_l_str = f"**${r['p_l']:,.2f}**" if r['p_l'] > 0 else f"${r['p_l']:,.2f}"
            
            # Combine icon with top pick for clarity
            ai_pick_with_status = f"{r['result_status']} {r['ai_top_pick']}"
            
            # Format ROIs with signs
            ai_roi_str = f"+{r['ai_roi']}%" if r['ai_roi'] > 0 else f"{r['ai_roi']}%"
            k_roi_str = f"+{r['kelly_roi']}%" if r['kelly_roi'] > 0 else f"{r['kelly_roi']}%"
            if r['kelly_stake'] == 0: k_roi_str = "--"

            report += f"| **R{r['race_no']}** | {r['official_result']} | {ai_pick_with_status} | {k_stake} | {p_l_str} | {ai_roi_str} | {k_roi_str} |\n"
            
        report += f"\n\n*Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        return report

    def evaluate_shadow(self, date_str: str, venue: str) -> List[Dict]:
        """Evaluates shadow (A/B) predictions for the same race day."""
        results_list = []
        pattern = f"prediction_{date_str}_{venue}_R*_shadow.json"
        shadow_files = sorted(list(self.predictions_dir.glob(pattern)))

        if not shadow_files:
            return []

        for pred_file in shadow_files:
            try:
                with open(pred_file, "r", encoding="utf-8") as f:
                    pred_data = json.load(f)

                race_id = pred_data["race_id"]
                race_no = race_id.split("_R")[-1]
                rec_bet = pred_data.get("recommended_bet", "")

                if not rec_bet or rec_bet == "NO BET":
                    continue

                result_file = self.results_dir / f"results_{race_id}.json"
                if not result_file.exists():
                    continue

                with open(result_file, "r", encoding="utf-8") as f:
                    result_data = json.load(f)

                import re
                numbers = re.findall(r'\d+', rec_bet)
                selection = numbers[0] if numbers else ""

                profit_dividend = self.calculate_profit(rec_bet, result_data)
                status = "WIN" if profit_dividend > 0 else "LOSS"
                ai_p_l = profit_dividend - 10.0 if profit_dividend > 0 else -10.0
                ai_roi = (ai_p_l / 10.0) * 100

                official_win = next((h["horse_no"] for h in result_data.get("results", []) if h.get("plc") == "1"), "")

                results_list.append({
                    "race_no": race_no,
                    "race_id": race_id,
                    "official_result": f"WIN {official_win}" if official_win else "--",
                    "ai_top_pick": rec_bet,
                    "ai_roi": round(ai_roi, 1),
                    "model": pred_data.get("gemini_model", "shadow"),
                })
            except Exception as e:
                print(f"Error evaluating shadow {pred_file.name}: {e}")

        return results_list

    def format_ab_comparison(self, date_str: str, venue: str, primary: List[Dict], shadow: List[Dict]) -> str:
        """Generates A/B comparison section for the report."""
        if not shadow:
            return ""

        # Build lookup by race_no
        shadow_by_race = {r["race_no"]: r for r in shadow}
        primary_by_race = {r["race_no"]: r for r in primary}
        all_races = sorted(set(list(shadow_by_race.keys()) + list(primary_by_race.keys())), key=int)

        p_wins = sum(1 for r in primary if "WIN" not in r.get("result_status", "") or "WIN" in r.get("result_status", ""))
        # Recalculate properly
        p_wins = sum(1 for r in primary if "✅" in r.get("result_status", ""))
        s_wins = sum(1 for r in shadow if r["ai_roi"] > 0)

        p_model = Config.GEMINI_MODEL.split("/")[-1] if "/" in Config.GEMINI_MODEL else Config.GEMINI_MODEL
        s_model = Config.SHADOW_MODEL

        section = f"\n## 🔬 A/B Model Comparison\n"
        section += f"| | **{p_model}** (Primary) | **{s_model}** (Shadow) |\n"
        section += f"| :--- | :--- | :--- |\n"
        section += f"| **Wins** | {p_wins}/{len(primary)} | {s_wins}/{len(shadow)} |\n"

        p_roi = sum(r['ai_roi'] for r in primary) / len(primary) if primary else 0
        s_roi = sum(r['ai_roi'] for r in shadow) / len(shadow) if shadow else 0
        section += f"| **Avg AI ROI** | {p_roi:.1f}% | {s_roi:.1f}% |\n\n"

        section += "| Race | Official | Primary Pick | Shadow Pick | Primary | Shadow |\n"
        section += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"

        for rn in all_races:
            p = primary_by_race.get(rn, {})
            s = shadow_by_race.get(rn, {})
            official = p.get("official_result", s.get("official_result", "--"))
            p_pick = p.get("ai_top_pick", "--")
            s_pick = s.get("ai_top_pick", "--")
            p_r = f"{p.get('ai_roi', 0):.0f}%" if p else "--"
            s_r = f"{s.get('ai_roi', 0):.0f}%" if s else "--"

            # Highlight if picks differ
            if p_pick != s_pick and p_pick != "--" and s_pick != "--":
                p_pick = f"**{p_pick}**"
                s_pick = f"**{s_pick}**"

            section += f"| R{rn} | {official} | {p_pick} | {s_pick} | {p_r} | {s_r} |\n"

        return section

    def calculate_profit(self, rec_bet: str, result_data: Dict[str, Any]) -> float:
        """
        Calculates the gross payout for a specific bet.
        Handles variations like "WIN 9", "WIN - Horse 5", "QUINELLA 3-10"
        """
        import re
        dividends = result_data.get("dividends", {})
        
        # Clean the string and find the bet type
        rec_bet_up = rec_bet.upper()
        bet_type = None
        for bt in ["WIN", "PLACE", "QUINELLA"]:
            if bt in rec_bet_up:
                bet_type = bt
                break
        
        if not bet_type:
            return 0.0

        # Extract all numbers from the string
        numbers = re.findall(r'\d+', rec_bet)
        if not numbers:
            return 0.0

        # Handle WIN / PLACE payouts
        if bet_type in ["WIN", "PLACE"]:
            selection = numbers[0]
            pool = dividends.get(bet_type, [])
            for div in pool:
                if div.get("combination") == selection:
                    return float(div["dividend"])
            
            # Fallback for WIN bets: Use win_odds if dividends are missing
            if bet_type == "WIN":
                for res in result_data.get("results", []):
                    if res.get("plc") == "1" and str(res.get("horse_no")) == selection:
                        return float(res.get("win_odds", "0")) * 10.0
        
        # Handle QUINELLA (e.g., "QUINELLA 3-10")
        elif bet_type == "QUINELLA":
            pool = dividends.get("QUINELLA", [])
            # Take the first two numbers found
            if len(numbers) < 2: return 0.0
            sel_parts = sorted([numbers[0], numbers[1]])
            
            for div in pool:
                div_parts = sorted(div["combination"].split(","))
                if sel_parts == div_parts:
                    return float(div["dividend"])

        return 0.0

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate Betting Performance")
    parser.add_argument("--date", type=str, default="2026-03-22", help="Date in YYYY-MM-DD format")
    parser.add_argument("--venue", type=str, default="ST", help="Venue (ST or HV)")
    args = parser.parse_args()

    evaluator = BettingEvaluator()
    data = evaluator.evaluate_day(args.date, args.venue)
    report = evaluator.format_markdown_report(args.date, args.venue, data)
    print(report)
