import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.backtest_engine import BacktestEngine

async def run_baseline():
    """
    Runs a baseline backtest for the 2024-2025 transition period.
    This period is crucial for validating our 'Modern HKJC' model weights.
    """
    print("="*60)
    print("HKJC BASELINE BACKTEST: 2024-2025 SEASON")
    print("="*60)

    # 1. Run for Late 2024 (September to December)
    print("\n--- Phase 1: Late 2024 (Season Start) ---")
    engine_2024 = BacktestEngine(fixtures_path="data/fixtures_2024.json")
    await engine_2024.run_backtest(start_date="2024-09-01", end_date="2024-12-31")

    # 2. Run for Early 2025 (January to March)
    print("\n--- Phase 2: Early 2025 (Current Trend) ---")
    engine_2025 = BacktestEngine(fixtures_path="data/fixtures_2025.json")
    await engine_2025.run_backtest(start_date="2025-01-01", end_date="2025-03-15")

    print("\n" + "="*60)
    print("BASELINE BACKTEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_baseline())
