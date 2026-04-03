import asyncio
import pandas as pd
from services.live_audit_service import live_audit_service
from unittest.mock import MagicMock, patch, AsyncMock

async def test_scheduler_filtering():
    print("--- Testing Live Audit Filtering (Selective Alerts) ---")
    
    # 1. Mock the ConsensusAgent to return a 'Grade [B]' (Should NOT notify)
    with patch('services.live_audit_service.consensus_agent') as mock_agent:
        with patch('services.live_audit_service.telegram_service') as mock_telegram:
            mock_telegram.send_message = AsyncMock()
            # Use a real async function for mocking
            async def mock_get_consensus(*args, **kwargs):
                return ("CAUTION", "Grade [B] — Reasoning...")
            mock_agent.get_consensus = mock_get_consensus
            
            # Mock the monitor to return a -25% drop (Enough to trigger audit)
            live_audit_service.monitor.update_race_state = MagicMock(return_value=MagicMock(
                movements={'4': MagicMock(movement_pct=-0.25, initial_odds=10.0, current_odds=7.5, trend='late_money')}
            ))
            
            # Mock the data loader
            live_audit_service._load_race_data = MagicMock(return_value=pd.DataFrame([{'horse_no': 4}]))
            
            print("Running Audit for Grade [B]...")
            await live_audit_service.audit_late_money("2026-04-06_ST_R11", "4", "2026-04-06", "ST", 11)
            
            if not mock_telegram.send_message.called:
                print("✅ SUCCESS: Telegram was correctly SILENCED for Grade [B].")
            else:
                print("❌ FAILURE: Telegram was sent for a Low-Conviction Grade [B].")

    # 2. Mock the ConsensusAgent to return a 'Grade [S]' (Should NOTIFY)
    with patch('services.live_audit_service.consensus_agent') as mock_agent:
        with patch('services.live_audit_service.telegram_service') as mock_telegram:
            async def mock_get_consensus_s(*args, **kwargs):
                return ("CONFIRMED", "Grade [S] — Extreme Smart Money detected!")
            mock_agent.get_consensus = mock_get_consensus_s
            
            # Mock the monitor
            live_audit_service.monitor.update_race_state = MagicMock(return_value=MagicMock(
                movements={'4': MagicMock(movement_pct=-0.35, initial_odds=10.0, current_odds=6.5, trend='late_money')}
            ))
            
            print("\nRunning Audit for Grade [S]...")
            await live_audit_service.audit_late_money("2026-04-06_ST_R11", "4", "2026-04-06", "ST", 11)
            
            if mock_telegram.send_message.called:
                print("✅ SUCCESS: Telegram ALERT was sent for High-Conviction Grade [S].")
            else:
                print("❌ FAILURE: Telegram was silenced for a High-Conviction Grade [S].")

if __name__ == "__main__":
    asyncio.run(test_scheduler_filtering())
