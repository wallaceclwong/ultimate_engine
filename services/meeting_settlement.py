import asyncio
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from loguru import logger

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config
from services.results_ingest import ResultsIngest
from services.betting_evaluator import BettingEvaluator
from services.firestore_service import FirestoreService
from services.rl_optimizer import RLOptimizer
from services.bankroll_manager import BankrollManager

class MeetingSettlement:
    def __init__(self, headless=True):
        self.results_ingest = ResultsIngest(headless=headless)
        self.evaluator = BettingEvaluator()
        self.firestore = FirestoreService()
        self.bankroll_manager = BankrollManager()
        self.reports_dir = Path("data/reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    async def settle_meeting(self, date_str: str, venue: str):
        """
        Orchestrates full meeting settlement: fetch results, evaluate, and report.
        """
        logger.info(f"🏁 Starting Settlement for {date_str} ({venue})...")
        
        # 1. Fetch results for all races (assuming 9-11 races)
        max_races = 11 if venue == "ST" else 9
        for r in range(1, max_races + 1):
            race_id = f"{date_str}_{venue}_R{r}"
            filename = f"data/results/results_{race_id}.json"
            
            if os.path.exists(filename):
                logger.info(f"Results for R{r} already exists locally. Skipping scrape.")
                continue

            logger.info(f"Scraping results for R{r}...")
            # We use the results_ingest script's main logic or fetch_results
            try:
                res_data = await self.results_ingest.fetch_results(date_str, venue, r)
                if res_data:
                    os.makedirs("data/results", exist_ok=True)
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(res_data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to fetch results for R{r}: {e}")

        # 2. Run Evaluation
        logger.info("Evaluating betting performance...")
        results_list = self.evaluator.evaluate_day(date_str, venue)
        
        if not results_list:
            logger.warning(f"No results found for settlement on {date_str}")
            return False

        # 3. Generate Markdown Report
        logger.info("Generating Markdown report...")
        report_md = self.evaluator.format_markdown_report(date_str, venue, results_list)
        
        # 3b. A/B Shadow Evaluation
        shadow_results = self.evaluator.evaluate_shadow(date_str, venue)
        if shadow_results:
            logger.info(f"A/B shadow: {len(shadow_results)} shadow predictions evaluated")
            ab_section = self.evaluator.format_ab_comparison(date_str, venue, results_list, shadow_results)
            report_md += ab_section

        # Save locally
        report_file = self.reports_dir / f"report_{date_str}_{venue}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_md)
        logger.info(f"Report saved to {report_file}")

        # 4. Sync to Firestore (meeting_reports collection) & Bankroll
        try:
            total_stake = sum(r['kelly_stake'] for r in results_list)
            total_p_l = sum(r['p_l'] for r in results_list)
            report_id = f"{date_str}_{venue}"
            
            # Apply to Bankroll Manager (MEETING BY MEETING ROLL)
            self.bankroll_manager.add_transaction(report_id, total_p_l, f"Meeting Settlement: {venue}")
            
            report_data = {
                "meeting_date": date_str,
                "venue": venue,
                "total_races": len(results_list),
                "total_stake": total_stake,
                "net_profit": total_p_l,
                "overall_roi": (total_p_l / total_stake * 100) if total_stake > 0 else 0,
                "markdown": report_md,
                "updated_at": datetime.now().isoformat()
            }
            
            report_id = f"{date_str}_{venue}"
            self.firestore.upsert("meeting_reports", report_id, report_data)
            logger.info(f"✅ Settlement synced to Firestore: {report_id}")
        except Exception as e:
            logger.error(f"Failed to sync settlement to Firestore: {e}")
            return False

        # 5. Auto-recalibrate RL biases using latest results
        try:
            logger.info("🧠 Running RL bias recalibration...")
            optimizer = RLOptimizer()
            optimizer.optimize_from_past_days(days=30)
            logger.info("✅ RL biases recalibrated with latest 30 days of data")
        except Exception as e:
            logger.error(f"⚠️ RL recalibration failed (non-critical): {e}")

        return True

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="HKJC Meeting Settlement")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--venue", type=str, default="ST")
    args = parser.parse_args()

    settlement = MeetingSettlement()
    await settlement.settle_meeting(args.date, args.venue)

if __name__ == "__main__":
    asyncio.run(main())
