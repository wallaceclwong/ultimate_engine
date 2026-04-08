import asyncio
import re
import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.browser_manager import BrowserManager

class PedigreeScraper:
    def __init__(self, headless=True):
        self.browser_mgr = BrowserManager(headless=headless)
        self.cache_file = Path("data/pedigree_cache.json")
        self.cache = self._load_cache()

    def _load_cache(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self):
        os.makedirs(self.cache_file.parent, exist_ok=True)
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2)

    async def fetch_horse_pedigree(self, horse_id: str, page=None):
        """
        Scrapes the HKJC horse profile page for pedigree and origin data.
        """
        if not horse_id or horse_id == "Unknown":
            return None

        # Strategically build URLs to try
        urls_to_try = []
        if "_" in horse_id:
            # It's already a full ID
            urls_to_try.append(f"https://racing.hkjc.com/en-us/local/information/otherhorse?horseid={horse_id}")
        else:
            # It's a brand code (e.g. H256). Try recent years as HKJC uses them in the URL.
            current_year = datetime.now().year
            for y in range(current_year, current_year - 5, -1):
                urls_to_try.append(f"https://racing.hkjc.com/en-us/local/information/otherhorse?horseid=HK_{y}_{horse_id}")
            # Final fallback: Search redirect
            urls_to_try.append(f"https://racing.hkjc.com/racing/information/English/Horse/Horse.aspx?HorseId={horse_id}")
        
        own_page = False
        if not page:
            page = await self.browser_mgr.get_page()
            own_page = True

        pedigree = None
        for url in urls_to_try:
            print(f"  [TRY] {horse_id} -> {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                
                # Check for the verified 'horsemaininfo' table
                table = await page.query_selector("table.horsemaininfo")
                if not table:
                    # Try the alternative older layout class
                    table = await page.query_selector("table.horseProfile")
                
                if not table:
                    continue # Try next URL

                content = await table.inner_text()
                
                # If content is empty or doesn't have "Sire", it might be a redirect to home
                if "Sire" not in content:
                    continue

                pedigree = {
                    "sire": "Unknown",
                    "dam": "Unknown",
                    "dam_sire": "Unknown",
                    "origin": "Unknown",
                    "color": "Unknown",
                    "sex": "Unknown",
                    "import_type": "Unknown",
                    "last_updated": datetime.now().isoformat()
                }

                def extract(label, text):
                    pattern = rf"{label}\s*:\s*([^\n\t\r|]+)"
                    m = re.search(pattern, text, re.IGNORECASE)
                    if m:
                        val = m.group(1).strip()
                        val = re.split(r'\s{2,}', val)[0]
                        return val
                    return "Unknown"

                pedigree["origin"] = extract("Country of Origin / Age", content)
                pedigree["color"] = extract("Color / Sex", content)
                pedigree["sire"] = extract("Sire", content)
                pedigree["dam"] = extract("Dam", content)
                pedigree["dam_sire"] = extract("Dam's Sire", content)
                pedigree["import_type"] = extract("Import Type", content)

                if "Dam's Sire" in pedigree["dam"]:
                    pedigree["dam"] = pedigree["dam"].split("Dam's Sire")[0].strip()

                if pedigree["sire"] != "Unknown":
                    print(f"    [OK] Sire: {pedigree['sire']} | Dam: {pedigree['dam']}")
                    break # Found it!

            except Exception as e:
                print(f"    [INFO] URL failed for {horse_id}: {str(e)[:50]}")
                continue
        
        if own_page:
            await page.close()
        return pedigree

    async def run_batch(self, horse_ids: list):
        """Processes a list of horse IDs."""
        page = await self.browser_mgr.get_page()
        for idx, h_id in enumerate(horse_ids):
            if h_id in self.cache:
                continue
            
            p_data = await self.fetch_horse_pedigree(h_id, page=page)
            if p_data:
                self.cache[h_id] = p_data
                # Save immediately for resilience
                self._save_cache()
            
            # Anti-scraping delay
            await asyncio.sleep(2)
        
        await page.close()
        await self.browser_mgr.stop()

def get_unique_horse_ids():
    ids = set()
    # 1. From racecards
    racecard_dir = Path("data/racecards")
    if racecard_dir.exists():
        for f in racecard_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as j:
                    data = json.load(j)
                    for h in data.get("racecard", []):
                        # Try direct key
                        if h.get("horse_id"): ids.add(h["horse_id"])
                        # Try parsing from "horse" name
                        elif h.get("horse"):
                            match = re.search(r'\(([A-Z0-9]+)\)', h["horse"])
                            if match: ids.add(match.group(1))
            except: pass

    # 2. From results (for historical backfill)
    results_dir = Path("data/results")
    if results_dir.exists():
        for f in results_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as j:
                    data = json.load(j)
                    for h in data.get("results", []):
                        if h.get("horse_id"): ids.add(h["horse_id"])
                        elif h.get("horse"):
                            match = re.search(r'\(([A-Z0-9]+)\)', h["horse"])
                            if match: ids.add(match.group(1))
            except: pass
    
    return sorted(list(ids))

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="+", help="Specific horse IDs to scrape")
    parser.add_argument("--all", action="store_true", help="Scrape all new horses from data files")
    args = parser.parse_args()

    scraper = PedigreeScraper(headless=True)
    
    if args.ids:
        to_scrape = args.ids
    elif args.all:
        to_scrape = get_unique_horse_ids()
    else:
        print("Usage: python scripts/scrape_pedigree.py --all OR --ids HK_2023_H001")
        return

    print(f"Found {len(to_scrape)} horses to check...")
    await scraper.run_batch(to_scrape)

if __name__ == "__main__":
    asyncio.run(main())
