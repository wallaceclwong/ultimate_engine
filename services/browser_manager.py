import asyncio
import os
from playwright.async_api import async_playwright, BrowserContext, Page, Browser, Playwright
from typing import Optional, Tuple
from pathlib import Path
import time

class BrowserManager:
    """
    Unified manager for Playwright browser life-cycles.
    Ensures playwright.stop() is called and allows reuse of browser sessions.
    """
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self._user_data_dir: Optional[Path] = None
    
    # Class-level cache to persist across reloads or multiple instances
    _contexts = {} # session_id -> BrowserContext

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    def _get_proxy_config(self):
        """Returns proxy config from PROXY_URL env var if set."""
        proxy_url = os.getenv("PROXY_URL")
        if proxy_url:
            # Format: http://user:pass@host:port
            return {"server": proxy_url}
        return None

    async def start(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
        if not self.browser:
            proxy = self._get_proxy_config()
            launch_opts = {"headless": self.headless}
            if proxy:
                launch_opts["proxy"] = proxy
            self.browser = await self.playwright.chromium.launch(**launch_opts)
        return self

    async def stop(self):
        for context in BrowserManager._contexts.values():
            try: await context.close()
            except: pass
        BrowserManager._contexts = {}
        if self.browser:
            try: await self.browser.close()
            except: pass
            self.browser = None
        if self.playwright:
            try: await self.playwright.stop()
            except: pass
            self.playwright = None

    async def get_page(self) -> Page:
        """Returns a new page from the current browser instance."""
        if not self.browser:
            await self.start()
        page = await self.browser.new_page()
        # Injects common headers/detection evasion
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        # Block heavy resources when using proxy to save bandwidth
        if os.getenv("PROXY_URL"):
            await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}", lambda route: route.abort())
            await page.route("**/*.css", lambda route: route.abort())
        return page

    async def get_persistent_context(self, session_id: str = "default") -> Tuple[BrowserContext, Page]:
        """Returns a persistent context for login-heavy tasks. Reuses if already active."""
        if session_id in BrowserManager._contexts:
            try:
                context = BrowserManager._contexts[session_id]
                # Test if still connected
                page = await context.new_page()
                return context, page
            except:
                del BrowserManager._contexts[session_id]

        if not self.playwright:
            self.playwright = await async_playwright().start()
        
        user_data_dir = Path(f"data/browser_session_{session_id}")
        user_data_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            context = await self.playwright.chromium.launch_persistent_context(
                str(user_data_dir.absolute()),
                headless=self.headless,
                viewport={'width': 1280, 'height': 800},
                args=["--disable-blink-features=AutomationControlled"]
            )
            BrowserManager._contexts[session_id] = context
            page = context.pages[0] if context.pages else await context.new_page()
            return context, page
        except Exception as e:
            if "lock" in str(e).lower():
                print(f"CRITICAL: Browser profile {session_id} is locked. Close other HKJC browser windows.")
            raise e
