"""
Standalone on-demand profile updater.

Runs immediately — no scheduler, no delays between steps.
Updates resume, headline, and summary all at once.

Usage:
    python update_profile_now.py
"""

import logging
import sys
import traceback
from pathlib import Path

# Make sure project root is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent))

from services.browser.browser_service import BrowserService
from services.auth.login_service import LoginService
from services.profile.profile_service import ProfileService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=== On-demand profile update started ===")

    browser = BrowserService()
    page = browser.launch()

    try:
        LoginService(page).ensure_logged_in()

        result = ProfileService(page).update(force_all=True, skip_gaps=True)

        logger.info("=== Profile update complete ===")
        logger.info("Headline  : %s", result["new_headline"])
        logger.info("Summary   : %s", (result["new_summary"] or "")[:120] + "…")
        logger.info("Resume    : %s", result["resume_path"])

    except Exception:
        logger.error("Profile update failed:\n%s", traceback.format_exc())
        sys.exit(1)
    finally:
        browser.close()


if __name__ == "__main__":
    main()
