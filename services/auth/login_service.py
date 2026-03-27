import logging
from playwright.sync_api import Page
from config.settings import NAUKRI_LOGIN_URL, NAUKRI_PROFILE_URL, NAUKRI_EMAIL, NAUKRI_PASSWORD, SESSION_FILE
from services.locators.naukri_locators import LoginLocators, OTPLocators
from core.utils import try_selectors

logger = logging.getLogger(__name__)

# How long (ms) to wait for OTP to be entered manually
OTP_MANUAL_TIMEOUT_MS = 120_000


class LoginService:
    """Handles Naukri session detection and login."""

    def __init__(self, page: Page):
        self.page = page

    # ── Public ────────────────────────────────────────────────────────────────

    def ensure_logged_in(self):
        """Check session by navigating to profile URL.

        If we land on the profile page, session is valid — no login needed.
        If Naukri redirects to nlogin, session is missing/expired — fill login form.
        """
        self.page.goto(NAUKRI_PROFILE_URL, wait_until="domcontentloaded")

        if self.page.url.startswith(NAUKRI_PROFILE_URL):
            logger.info("Session active — already on profile page")
            return

        logger.info("Session invalid — navigating to login page")
        self.page.goto(NAUKRI_LOGIN_URL, wait_until="domcontentloaded")
        self._fill_and_submit()

    # ── Private ───────────────────────────────────────────────────────────────

    def _fill_and_submit(self):
        # 1. Fill email
        email_field = try_selectors(self.page, LoginLocators.EMAIL, timeout=3000)
        if not email_field:
            raise RuntimeError("Email input field not found")
        email_field.fill(NAUKRI_EMAIL)
        self.page.wait_for_timeout(400)

        # 2. Fill password
        pwd_field = try_selectors(self.page, LoginLocators.PASSWORD, timeout=3000)
        if not pwd_field:
            raise RuntimeError("Password input field not found")
        pwd_field.fill(NAUKRI_PASSWORD)
        self.page.wait_for_timeout(400)

        # 3. Submit
        submit = try_selectors(self.page, LoginLocators.SUBMIT, timeout=3000)
        if not submit:
            raise RuntimeError("Login submit button not found")
        submit.click()

        # 4. Handle OTP if Naukri shows the verification screen
        self._handle_otp_if_present()

        # 5. Wait for redirect away from login page
        try:
            self.page.wait_for_function(
                "() => !window.location.href.includes('nlogin')",
                timeout=30000,
            )
        except Exception:
            raise RuntimeError("Login failed — still on login page after submit")

        self.page.context.storage_state(path=SESSION_FILE)
        logger.info("Login successful — session saved to %s", SESSION_FILE)

    def _handle_otp_if_present(self):
        """If OTP screen appears, wait for the user to enter it manually."""
        try:
            self.page.wait_for_selector(OTPLocators.SPLIT_FIELDS[0], timeout=5000)
            logger.warning(
                "OTP screen detected. Please enter the OTP in the browser window. "
                "Waiting up to %d seconds...",
                OTP_MANUAL_TIMEOUT_MS // 1000,
            )
            # Wait until OTP screen is gone (user submitted) or timeout
            self.page.wait_for_function(
                "() => !document.querySelector('input#Input_1')",
                timeout=OTP_MANUAL_TIMEOUT_MS,
            )
            logger.info("OTP step completed")
        except Exception:
            # OTP screen never appeared — normal password login
            pass
