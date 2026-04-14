import asyncio
import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from consensus_agent import consensus_agent

async def test_war_room():
    print("--- WAR ROOM DRY RUN: Expert Audit & Long-Term Memory ---")
    
    # 1. Create a mock race data for Sunday R1
    race_data = pd.DataFrame([{
        "horse_no": "5",
        "horse_name": "SPICY DART",
        "horse_id": "J123",
        "trainer": "P C Ng",
        "jockey": "Z Purton",
        "win_odds": 4.5,
        "draw": 2,
        "rank": 1,
        "fair_odds": 3.2,
        "value_mult": 1.4,
        "venue": "ST",
        "distance": 1200,
        "track_type": "Turf"
    }])
    
    print(f"Targeting: #5 SPICY DART (Sunday R1 Pilot)")
    print("Handshaking with MemPalace on Ubuntu VM...")
    
    try:
        # 2. Trigger the Audit (Will search MemPalace then hit DeepSeek-R1)
        verdict, reasoning = await consensus_agent.get_consensus(race_data, "5")
        
        print("\n" + "="*60)
        print(f"VERDICT: {verdict}")
        print(f"EXPERT REASONING:\n{reasoning}")
        print("="*60)
        
        if verdict in ["CONFIRMED", "CAUTION"]:
            print("\nREADY: War Room Link is Active.")
        else:
            print("\nALERT: Audit returned VETO/ERROR.")
            
    except Exception as e:
        print(f"\nFAILURE: {e}")

if __name__ == "__main__":
    asyncio.run(test_war_room())
