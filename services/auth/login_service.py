import email
import imaplib
import logging
import re
import time
from playwright.sync_api import Page
from config.settings import NAUKRI_LOGIN_URL, NAUKRI_PROFILE_URL, NAUKRI_EMAIL, NAUKRI_PASSWORD, GMAIL_APP_PASSWORD, SESSION_FILE
from services.locators.naukri_locators import LoginLocators, OTPLocators
from core.utils import try_selectors

logger = logging.getLogger(__name__)

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
OTP_SENDER = "info@naukri.com"
OTP_SUBJECT = "Your OTP for logging in Naukri account"
# How many seconds to keep polling inbox for the OTP email
OTP_FETCH_TIMEOUT_S = 60
OTP_POLL_INTERVAL_S = 4


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
        """If OTP screen appears, fetch the OTP from Gmail and fill it automatically."""
        try:
            self.page.wait_for_selector(OTPLocators.SPLIT_FIELDS[0], timeout=5000)
        except Exception:
            # OTP screen never appeared — normal password login
            return

        logger.info("OTP screen detected — fetching OTP from Gmail...")
        otp = self._fetch_otp_from_gmail()
        if not otp or len(otp) != 6:
            raise RuntimeError("Could not retrieve a valid 6-digit OTP from Gmail")

        logger.info("OTP retrieved — filling fields")
        for i, digit in enumerate(otp):
            field = self.page.locator(OTPLocators.SPLIT_FIELDS[i])
            field.fill(digit)
            self.page.wait_for_timeout(120)

        submit = try_selectors(self.page, OTPLocators.SUBMIT, timeout=3000)
        if not submit:
            raise RuntimeError("OTP submit button not found")
        submit.click()
        logger.info("OTP submitted successfully")

    def _fetch_otp_from_gmail(self) -> str:
        """Poll Gmail inbox until the Naukri OTP email arrives, then return the 6-digit code."""
        deadline = time.time() + OTP_FETCH_TIMEOUT_S
        while time.time() < deadline:
            otp = self._try_read_otp_email()
            if otp:
                return otp
            logger.debug("OTP email not found yet — retrying in %ds", OTP_POLL_INTERVAL_S)
            time.sleep(OTP_POLL_INTERVAL_S)
        raise RuntimeError("OTP email did not arrive within %d seconds" % OTP_FETCH_TIMEOUT_S)

    def _try_read_otp_email(self) -> str | None:
        """Connect to Gmail via IMAP and extract the OTP from the latest Naukri OTP email."""
        try:
            with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as mail:
                mail.login(NAUKRI_EMAIL, GMAIL_APP_PASSWORD)
                mail.select("INBOX")

                # Search for the latest email matching sender + subject
                _, uids = mail.uid(
                    "search", None,
                    f'FROM "{OTP_SENDER}"',
                    f'SUBJECT "{OTP_SUBJECT}"',
                )
                uid_list = uids[0].split()
                if not uid_list:
                    return None

                # Take the most recent match
                latest_uid = uid_list[-1]
                _, msg_data = mail.uid("fetch", latest_uid, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                body = self._extract_text_body(msg)
                return self._parse_otp(body)
        except Exception as exc:
            logger.warning("IMAP fetch error: %s", exc)
            return None

    @staticmethod
    def _extract_text_body(msg: email.message.Message) -> str:
        """Return the plain-text body of an email message."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    charset = part.get_content_charset() or "utf-8"
                    return part.get_payload(decode=True).decode(charset, errors="replace")
        else:
            charset = msg.get_content_charset() or "utf-8"
            return msg.get_payload(decode=True).decode(charset, errors="replace")
        return ""

    @staticmethod
    def _parse_otp(body: str) -> str | None:
        """Extract the standalone 6-digit OTP from the email body."""
        # The OTP appears on its own line e.g. "178180"
        match = re.search(r"(?<!\d)(\d{6})(?!\d)", body)
        return match.group(1) if match else None
