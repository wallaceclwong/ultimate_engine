import asyncio
import pandas as pd
from consensus_agent import consensus_agent

async def test_live_reasoning():
    print("--- Testing Live Smart Money Reasoning ---")
    
    # 1. Mock Race Data (Race 11, April 6th)
    # Horse: AERODYNAMICS (#4)
    race_data = pd.DataFrame([
        {
            "horse_no": 4,
            "horse_name": "AERODYNAMICS",
            "horse_id": "H456",
            "win_odds": 12.0,
            "fair_odds": 6.5,
            "value_mult": 1.85,
            "draw": 11,
            "rank": 1,
            "distance": 2000,
            "track_type": "Turf",
            "venue": "ST"
        },
        {
            "horse_no": 5,
            "horse_name": "FAMILY JEWEL",
            "horse_id": "H789",
            "win_odds": 4.5,
            "fair_odds": 5.0,
            "value_mult": 0.9,
            "draw": 6,
            "rank": 2,
            "distance": 2000,
            "track_type": "Turf",
            "venue": "ST"
        }
    ])

    # 2. Mock Market Context (30% Drop)
    market_context = {
        'movement': -0.30,
        'trend': 'late_money'
    }

    # 3. Trigger Reasoning
    print("Triggering DeepSeek-R1 Audit...")
    verdict, reasoning = await consensus_agent.get_consensus(race_data, 4, market_context)
    
    print(f"\nVerdict: {verdict}")
    print(f"Reasoning: {reasoning}")
    
    if "SIGNAL" in reasoning and "Grade" in reasoning:
        print("\n✅ SUCCESS: DeepSeek recognized the market signal.")
    else:
        print("\n❌ FAILURE: Missing signal or grade in output.")

if __name__ == "__main__":
    asyncio.run(test_live_reasoning())
