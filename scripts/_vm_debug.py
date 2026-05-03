import asyncio, sys
sys.path.insert(0, '/root/ultimate_engine')
from services.prediction_engine import PredictionEngine

async def test():
    pe = PredictionEngine()
    # Test load for R1
    data = await pe.load_race_data('2026-05-03', 'ST', 1)
    rc = data.get('racecard', {})
    print('racecard keys:', list(rc.keys()))
    print('horses count:', len(rc.get('horses', [])))
    print('first horse:', rc.get('horses', [{}])[0].get('horse_name') if rc.get('horses') else 'NONE')
    print()
    # Now test actual prediction
    pred = await pe.generate_prediction('2026-05-03', 'ST', 1)
    print('pred result:', pred)

asyncio.run(test())
