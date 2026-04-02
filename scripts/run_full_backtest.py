import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.backtest_engine import BacktestEngine
from services.rl_optimizer import RLOptimizer

async def run_full_chain():
    """
    Executes a continuous backtest from Sept 2024 to March 2026.
    Automatically transitions from baseline validation to modern trend capture.
    """
    print("="*60)
    print("HKJC FULL ERA BACKTEST: SEPT 2024 - MARCH 2026")
    print("="*60)

    # 1. Phase 1: Baseline (2024-2025 Season)
    print("\n[PHASE 1] Processing 2024-2025 Baseline...")
    # Note: Modern backtest engine handles multiple fixture files gracefully if called sequentially
    engine_24 = BacktestEngine(fixtures_path="data/fixtures_2024.json")
    await engine_24.run_backtest(start_date="2024-09-01", end_date="2024-12-31")
    
    engine_25_base = BacktestEngine(fixtures_path="data/fixtures_2025.json")
    await engine_25_base.run_backtest(start_date="2025-01-01", end_date="2025-07-31")

    # 2. Phase 2: Modern (2025-2026 Season)
    print("\n[PHASE 2] Processing 2025-2026 Modern Trends...")
    engine_25_modern = BacktestEngine(fixtures_path="data/fixtures_2025.json")
    await engine_25_modern.run_backtest(start_date="2025-09-01", end_date="2025-12-31")
    
    engine_26 = BacktestEngine(fixtures_path="data/fixtures_2026.json")
    await engine_26.run_backtest(start_date="2026-01-01", end_date="2026-03-20")

    # 3. Final Step: Global RL Optimization for Sunday
    print("\n" + "="*60)
    print("TRIGGERING FINAL AI OPTIMIZATION (PRE-SUNDAY)")
    print("="*60)
    optimizer = RLOptimizer()
    optimizer.optimize_from_past_days(days=600) # Covers the entire multi-season range

    print("\nMISSION COMPLETE: SYSTEM FULLY CALIBRATED FOR MARCH 22")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_full_chain())
