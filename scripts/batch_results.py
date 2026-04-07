import asyncio
import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))
from services.results_ingest import ResultsIngest

async def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime('%Y-%m-%d')
    venue = sys.argv[2] if len(sys.argv) > 2 else  ST
    
    print(f'--- Starting Batch Results Ingestion: {date_str} ({venue}) ---')
    ingest = ResultsIngest()
    
    results_dir = Path('data/results')
    results_dir.mkdir(parents=True, exist_ok=True)
    
    success_count = 0
    for race_no in range(1, 13):
        print(f'Fetching Race {race_no}...')
        try:
            data = await ingest.fetch_results(date_str, venue=venue, race_no=race_no)
            if data and data.get('results'):
                filename = results_dir / f'results_{date_str}_{venue}_R{race_no}.json'
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                print(f'  [OK] Saved to {filename.name}')
                success_count += 1
            else:
                print(f'  [SKIP] No results found (Race likely not run yet or EOF)')
                if race_no > 8: # If we miss 3 in a row at the end, stop
                    break
        except Exception as e:
            print(f'  [ERROR] Race {race_no}: {str(e)}')
            
    print(f'--- Ingestion Complete: {success_count} races processed ---')

if __name__ == '__main__':
    asyncio.run(main())
