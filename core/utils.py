import logging
import random
import time
from typing import List, Optional
from playwright.sync_api import Page, Locator

logger = logging.getLogger(__name__)

# Keyboard layout neighbours — used to generate realistic typos
_NEIGHBOURS: dict[str, str] = {
    'a': 'sqwz',  'b': 'vghn',  'c': 'xdfv',  'd': 'erfcs',
    'e': 'wrds',  'f': 'rdgv',  'g': 'tfhb',  'h': 'ygjn',
    'i': 'uojk',  'j': 'uhnki', 'k': 'ijlm',  'l': 'kop',
    'm': 'nkj',   'n': 'bhjm',  'o': 'iplk',  'p': 'ol',
    'q': 'wa',    'r': 'etdf',  's': 'awdze',  't': 'ryge',
    'u': 'yhij',  'v': 'cfgb',  'w': 'qase',  'x': 'zsdc',
    'y': 'tuhi',  'z': 'asx',
}


def human_type(page: Page, element, text: str):
    """Type text with realistic human keystroke rhythm.

    - Random delay 40–160ms between each character
    - 5% chance of a neighbouring-key typo followed by Backspace correction
    - 3% chance of a mid-word pause (300–900ms) to simulate thinking
    - Clicks the element first to ensure focus
    """
    element.click()
    time.sleep(random.uniform(0.1, 0.3))   # brief pause after click before typing

    for char in text:
        # Occasional typo on alphabetic characters
        if char.isalpha() and random.random() < 0.05:
            neighbours = _NEIGHBOURS.get(char.lower(), "")
            if neighbours:
                wrong = random.choice(neighbours)
                if char.isupper():
                    wrong = wrong.upper()
                page.keyboard.type(wrong)
                time.sleep(random.uniform(0.12, 0.35))
                page.keyboard.press("Backspace")
                time.sleep(random.uniform(0.08, 0.2))

        page.keyboard.type(char)
        time.sleep(random.uniform(0.04, 0.16))

        # Rare mid-word thinking pause
        if random.random() < 0.03:
            time.sleep(random.uniform(0.3, 0.9))


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
