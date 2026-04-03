import asyncio
import sys
import re
from pathlib import Path
from playwright.async_api import async_playwright

class HorseProfileService:
    def __init__(self):
        self.search_url = "https://racing.hkjc.com/racing/information/English/Horse/Horse.aspx"

    async def fetch_pedigree(self, horse_id):
        """Fetches Sire and Dam for a given horse ID by simulating a human search"""
        print(f"  [Profile] Scraping {horse_id} via Human Mimicry...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                # 1. Start at Search Page
                await page.goto(self.search_url, wait_until="domcontentloaded", timeout=45000)
                
                # 2. Select Brand Number
                # The radio button for brand number is usually near the input
                await page.click("input[value='BrandNumber']", timeout=5000)
                
                # 3. Enter ID
                await page.fill("input#txtBrandNo", horse_id)
                
                # 4. Press Enter or Click Search
                await page.keyboard.press("Enter")
                
                # 5. Wait for profile table to appear
                await page.wait_for_selector("table.horseProfile", timeout=15000)
                
                # 6. Extraction using robust siblings
                sire_locator = page.locator("td:has-text('Sire') + td + td")
                dam_locator = page.locator("td:has-text('Dam') + td + td")
                
                sire = await sire_locator.text_content(timeout=5000)
                dam = await dam_locator.text_content(timeout=5000)
                
                await browser.close()
                return {
                    "sire": sire.strip() if sire else "Unknown",
                    "dam": dam.strip() if dam else "Unknown"
                }
            except Exception as e:
                print(f"  [ERROR] Human Mimicry {horse_id} failed: {str(e)}")
                # One last attempt: Check if the direct URL works AFTER being on the search page
                try:
                    direct_url = f"{self.search_url}?HorseId={horse_id}"
                    await page.goto(direct_url, wait_until="networkidle", timeout=15000)
                    sire = await page.locator("td:has-text('Sire') + td + td").text_content(timeout=5000)
                    dam = await page.locator("td:has-text('Dam') + td + td").text_content(timeout=5000)
                    await browser.close()
                    return {"sire": sire.strip(), "dam": dam.strip()}
                except:
                    pass
                
                await browser.close()
                return {"sire": "Linkage Error", "dam": "Linkage Error"}

async def main():
    hid = sys.argv[1] if len(sys.argv) > 1 else "T233"
    svc = HorseProfileService()
    res = await svc.fetch_pedigree(hid)
    print(f"RESULT: {res}")

if __name__ == "__main__":
    asyncio.run(main())
