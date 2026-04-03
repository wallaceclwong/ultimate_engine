import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime
import os

async def fetch_monthly_schedule(month, year):
    """
    Fetches the HKJC race schedule for a given month and year.
    Returns a list of race objects.
    """
    url = "https://racing.hkjc.com/racing/information/English/Racing/Fixture.aspx"
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print(f"Navigating to {url}...")
        try:
            # Use domcontentloaded for faster/more reliable loading on complex sites
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"Initial navigation warning: {e}. Attempting to proceed anyway...")
            
        # Wait longer and see if data arrives
        await page.wait_for_timeout(5000) # 5 seconds extra wait
        
        # Take a screenshot to see what's on screen
        await page.screenshot(path="services/debug_screenshot.png")
        print("Debug screenshot saved to services/debug_screenshot.png")
            
        # Debug: Save page content to see what's actually rendered
        content = await page.content()
        with open("services/debug_page.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("Debug HTML saved to services/debug_page.html")
        
        # Wait for the table to be present
        # HKJC usually has a table with class 'fixture' or similar structure.
        # It's safer to wait for technical elements like 'td' that indicate data has arrived.
        await page.wait_for_selector("table", timeout=10000)
        
        # The fixture page uses a calendar table structure
        # We look for cells with class 'calendar'
        calendar_cells = await page.query_selector_all("td.calendar")
        
        march_fixtures = []
        
        for cell in calendar_cells:
            # Extract day number
            day_elem = await cell.query_selector(".f_fl")
            if not day_elem:
                continue
            day_text = await day_elem.inner_text()
            day_text = day_text.strip()
            
            # Extract venue and type from images
            img_elems = await cell.query_selector_all(".f_fr img")
            venue = ""
            race_type = ""
            for img in img_elems:
                alt = await img.get_attribute("alt")
                if alt:
                    alt = alt.upper()
                    if alt in ["ST", "HV"]:
                        venue = alt
                    elif alt in ["D", "N"]:
                        race_type = alt
            
            # Only add if we have a venue (meaning it's a race day)
            if venue:
                date_str = f"{day_text}/{month:02}/{year}"
                march_fixtures.append({
                    "date": date_str,
                    "venue": venue,
                    "type": race_type,
                    "ingested_at": datetime.now().isoformat()
                })
        
        await browser.close()
        return march_fixtures

async def fetch_season_fixtures():
    """
    Fetches the HKJC race schedule for the current/upcoming months in the season.
    """
    # Simply loops through current month + next 4 months for now
    now = datetime.now()
    all_fixtures = []
    
    for i in range(5):
        target_month = (now.month + i - 1) % 12 + 1
        target_year = now.year + (now.month + i - 1) // 12
        print(f"\n--- Fetching fixtures for {target_month:02}/{target_year} ---")
        fixtures = await fetch_monthly_schedule(target_month, target_year)
        if fixtures:
            all_fixtures.extend(fixtures)
            
    return all_fixtures

async def main():
    print("="*60)
    print("SEASON-WIDE SCHEDULE INGESTION")
    print("="*60)
    fixtures = await fetch_season_fixtures()
    
    if fixtures:
        print(f"\nSuccessfully found {len(fixtures)} fixtures for the season.")
        
        if not os.path.exists('data'):
            os.makedirs('data')
            
        with open('data/fixtures_season.json', 'w') as f:
            json.dump(fixtures, f, indent=2)
        print("\nStored results in data/fixtures_season.json")
    else:
        print("\nNo fixtures found. Please check connectivity.")

if __name__ == "__main__":
    asyncio.run(main())
