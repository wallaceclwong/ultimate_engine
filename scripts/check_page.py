import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from services.browser_manager import BrowserManager

async def check_page():
    bm = BrowserManager()
    ctx, page = await bm.get_persistent_context('check')
    await page.goto('https://racing.hkjc.com/en-us/local/information/racecard?racedate=2026/05/03&Racecourse=ST&RaceNo=1', timeout=60000)
    
    # Get page title
    title = await page.title()
    print(f"Page title: {title}")
    
    # Get page body text
    body_text = await page.inner_text('body')
    print(f"\nPage body (first 1000 chars):\n{body_text[:1000]}")
    
    # Look for horse-related elements
    divs_with_horse = await page.query_selector_all('div')
    print(f"\nFound {len(divs_with_horse)} div elements")
    
    # Check for specific keywords
    if 'Horse' in body_text:
        print("✓ 'Horse' found in page")
    if 'Jockey' in body_text:
        print("✓ 'Jockey' found in page")
    if 'racecard' in body_text.lower():
        print("✓ 'racecard' found in page")
    
    # Check if page might be blocked or showing error
    if 'error' in body_text.lower() or 'not available' in body_text.lower():
        print("⚠️ Page may be showing error or not available")
    
    # Try to find the "SETUP MY STARTER LIST" button and click it
    setup_button = await page.query_selector('a, button, div')
    if setup_button:
        button_text = await setup_button.inner_text()
        if 'SETUP' in button_text or 'STARTER' in button_text:
            print(f"Found setup button: {button_text[:50]}")
            # Try clicking it to see if it loads the horse data
            try:
                await setup_button.click()
                await page.wait_for_timeout(3000)
                # Check if tables appeared after click
                tables = await page.query_selector_all('table')
                print(f"Tables after click: {len(tables)}")
                if tables:
                    for i, t in enumerate(tables[:3]):
                        text = await t.inner_text()
                        print(f"Table {i}: {text[:300]}")
            except Exception as e:
                print(f"Click failed: {e}")
    
    # Check for any API calls or data attributes
    scripts = await page.query_selector_all('script')
    print(f"\nFound {len(scripts)} script tags")
    for i, script in enumerate(scripts[:5]):
        content = await script.inner_text()
        if 'horse' in content.lower() or 'racecard' in content.lower():
            print(f"Script {i} contains horse/racecard data: {len(content)} chars")
            print(f"Content preview: {content[:500]}")
    
    # Check if there's JSON data embedded
    all_text = await page.inner_text('body')
    if 'JSON' in all_text or 'json' in all_text:
        print("\nFound JSON references in page")
    
    # Try to find the actual horse data in the tables after click
    tables = await page.query_selector_all('table')
    print(f"\nTotal tables: {len(tables)}")
    for i, table in enumerate(tables):
        text = await table.inner_text()
        if 'Horse' in text or 'Jockey' in text or 'No.' in text:
            print(f"\n--- Horse Table {i} ---")
            print(text[:800])

if __name__ == "__main__":
    asyncio.run(check_page())
