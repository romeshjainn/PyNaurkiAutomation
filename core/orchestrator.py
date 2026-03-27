import logging
from services.browser.browser_service import BrowserService
from services.auth.login_service import LoginService
from services.profile.profile_service import ProfileService

logger = logging.getLogger(__name__)


class Orchestrator:
    """Wires all services together and defines the daily run flow.

    This is the only place services are composed — no service imports another.
    Add new steps here as services are built.
    """

    def run(self):
        browser = BrowserService()
        page = browser.launch()
        try:
            # Step 1: Ensure logged in — lands on profile page
            LoginService(page).ensure_logged_in()
            logger.info("On profile page: %s", page.url)

            # Step 2: Update profile — headline, summary, resume
            ProfileService(page).update()

            # Future steps will be added here:
            # JobService(page).apply_daily()

        except Exception as e:
            logger.error("Run failed: %s", e, exc_info=True)
        finally:
            browser.close()
