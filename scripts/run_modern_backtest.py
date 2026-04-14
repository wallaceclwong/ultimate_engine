import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.backtest_engine import BacktestEngine
from services.rl_optimizer import RLOptimizer

async def run_modern_cycle():
    """
    Runs a backtest for the 2025-2026 Modern Season.
    Captures the most recent trainer/jockey synergies and horse form trends.
    """
    print("="*60)
    print("HKJC MODERN SEASON BACKTEST: 2025-2026")
    print("="*60)

    # 1. Phase 1: Late 2025 (Season Kickoff)
    print("\n--- Phase 1: Sept - Dec 2025 ---")
    try:
        engine_2025 = BacktestEngine(fixtures_path="data/fixtures_2025.json")
        await engine_2025.run_backtest(start_date="2025-09-01", end_date="2025-12-31")
    except Exception as e:
        print(f"Skipping Phase 1 due to missing data: {e}")

    # 2. Phase 2: Early 2026 (Live Trend)
    print("\n--- Phase 2: Jan - Mar 2026 ---")
    engine_2026 = BacktestEngine(fixtures_path="data/fixtures_2026.json")
    await engine_2026.run_backtest(start_date="2026-01-01", end_date="2026-03-20")

    # 3. Final Step: Global RL Optimization
    print("\n" + "="*60)
    print("TRIGGERING GLOBAL AI OPTIMIZATION")
    print("="*60)
    optimizer = RLOptimizer()
    optimizer.optimize_from_past_days(days=200) # Cover the whole modern season

    print("\nMODERN BACKTEST CYCLE COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_modern_cycle())
