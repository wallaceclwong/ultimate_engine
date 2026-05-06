import asyncio
import json
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.live_odds_monitor import get_live_odds_monitor
from loguru import logger

async def test_baseline():
    monitor = get_live_odds_monitor()
    
    # Test Data: 2026-04-19 ST Race 10
    date_str = "2026-04-19"
    venue = "ST"
    race_no = 10
    
    logger.info("--- Testing Baseline Logic ---")
    
    # 1. Clear in-memory state to simulate fresh start
    monitor.race_states = {}
    
    # 2. Update race state (this should trigger load_baseline_odds)
    state = monitor.update_race_state(date_str, venue, race_no)
    
    if state:
        logger.info(f"Success! State created for {state.race_id}")
        logger.info(f"Timestamp: {state.timestamp}")
        logger.info(f"Number of movements: {len(state.movements)}")
        
        # Check if movements were calculated (they should be if baseline vs current is different)
        # Note: In a real test, 'current' might be the same as 'baseline' if only one snapshot exists
        # BUT we just added the prediction fallback, so let's see.
        
        for h, m in list(state.movements.items())[:3]:
            logger.info(f"  Horse #{h}: {m.initial_odds} -> {m.current_odds} ({m.movement_pct:+.1%})")
    else:
        logger.error("Failed to update race state.")

if __name__ == "__main__":
    asyncio.run(test_baseline())
