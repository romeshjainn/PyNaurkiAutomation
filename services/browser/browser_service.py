import logging
import os
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from config.settings import BROWSER_HEADLESS, SESSION_FILE

logger = logging.getLogger(__name__)


class BrowserService:
    """Manages the Playwright browser lifecycle.

    Usage:
        browser = BrowserService()
        page = browser.launch()
        ...
        browser.close()
    """

    def __init__(self):
        self._playwright = None
        self._browser: Browser = None
        self._context: BrowserContext = None
        self.page: Page = None

    def launch(self) -> Page:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=BROWSER_HEADLESS)

        session = SESSION_FILE if os.path.exists(SESSION_FILE) else None
        self._context = self._browser.new_context(
            storage_state=session,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
        )
        self.page = self._context.new_page()
        logger.info("Browser launched (headless=%s, session=%s)", BROWSER_HEADLESS, "loaded" if session else "none")
        return self.page

    def close(self):
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        logger.info("Browser closed")
