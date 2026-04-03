import asyncio
import os
import sys
from pathlib import Path

# Fix imports for VM structure
sys.path.append("/root/ultimate_engine")

from services.browser_manager import BrowserManager

async def debug_scrape(date_str="2026/04/06", venue="ST", race_no="11"):
    print(f"--- DEBUG VM SCRAPE (TR ENUM) ({date_str} {venue} R{race_no}) ---")
    bm = BrowserManager(headless=True)
    context, page = await bm.get_persistent_context(f"debug_tr_r{race_no}")
    
    url = f"https://racing.hkjc.com/en-us/local/information/racecard?racedate={date_str}&Racecourse={venue}&RaceNo={race_no}"
    print(f"Navigating to {url}...")
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        # Enumerate all rows in the document
        data = await page.evaluate(r'''() => {
            const allTr = Array.from(document.querySelectorAll('tr'));
            return allTr.map((tr, i) => {
                const text = tr.innerText.trim();
                return {
                    idx: i,
                    len: text.length,
                    text: text.substring(0, 50).replace(/\n/g, ' '),
                    classes: tr.className
                };
            }).filter(x => x.len > 0);
        }''')
        
        print(f"Found {len(data)} non-empty rows in the entire page.")
        for row in data:
            if row['len'] > 50:
                print(f"Row {row['idx']}: [len={row['len']}] [class='{row['classes']}'] {row['text']}...")

    except Exception as e:
        print(f"[ERROR] Debug scrape failed: {e}")
    finally:
        await bm.stop()

if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else "2026/04/06"
    venue = sys.argv[2] if len(sys.argv) > 2 else "ST"
    race = sys.argv[3] if len(sys.argv) > 3 else "11"
    asyncio.run(debug_scrape(date, venue, race))
