import logging
from typing import List, Optional
from playwright.sync_api import Page, Locator

logger = logging.getLogger(__name__)


def try_selectors(page: Page, selectors: List[str], timeout: int = 5000) -> Optional[Locator]:
    """Try each selector in order and return the first visible match.

    Args:
        page:      Playwright Page instance.
        selectors: Ordered list of CSS/Playwright selectors to try.
        timeout:   Max ms to wait per selector before trying the next.

    Returns:
        First matching visible Locator, or None if all selectors fail.
    """
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout)
            logger.debug("Matched selector: %s", selector)
            return locator
        except Exception:
            continue
    logger.warning("No selector matched from list: %s", selectors)
    return None
