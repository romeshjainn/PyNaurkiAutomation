"""Debug snapshot utility.

Call save_debug_snapshot(page, label) before raising any RuntimeError so you can
inspect the browser state at the point of failure.

Snapshots land in  <project_root>/debug/<YYYYMMDD_HHMMSS>_<label>/
  - screenshot.png  — full-page screenshot
  - page.html       — raw DOM at that moment

Browse them at  http://34.180.16.40:9876/
"""

import logging
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page

logger = logging.getLogger(__name__)

_DEBUG_DIR = Path(__file__).parent.parent / "debug"


def save_debug_snapshot(page: Page, label: str) -> str:
    """Capture a screenshot + HTML dump of the current page state.

    Args:
        page:  Playwright Page instance.
        label: Short identifier for what went wrong (e.g. "email_field_not_found").

    Returns:
        Path to the snapshot directory as a string.
    """
    # Sanitise label so it's safe as a directory name
    safe_label = re.sub(r"[^\w\-]", "_", label)[:60]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_dir = _DEBUG_DIR / f"{ts}_{safe_label}"
    snap_dir.mkdir(parents=True, exist_ok=True)

    # Screenshot
    try:
        page.screenshot(path=str(snap_dir / "screenshot.png"), full_page=True)
        logger.info("Debug screenshot saved → %s", snap_dir / "screenshot.png")
    except Exception as exc:
        logger.warning("Could not save debug screenshot: %s", exc)

    # HTML dump
    try:
        html = page.content()
        (snap_dir / "page.html").write_text(html, encoding="utf-8")
        logger.info("Debug HTML saved      → %s", snap_dir / "page.html")
    except Exception as exc:
        logger.warning("Could not save debug HTML: %s", exc)

    # Current URL
    try:
        (snap_dir / "url.txt").write_text(page.url, encoding="utf-8")
    except Exception:
        pass

    logger.info("Debug snapshot at: debug/%s_%s/", ts, safe_label)
    return str(snap_dir)
