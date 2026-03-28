"""
Handles easy-apply job application submission.

Responsibilities:
  - Detect easy-apply button on job detail page
  - Click apply and handle the modal/flow
  - Detect success or already-applied state
  - Handle errors: captcha (pause + alert), form errors, retries
"""

import logging
import time

from playwright.sync_api import Page

from core.utils import try_selectors
from services.jobs.job_chatbot import JobChatbot
from services.locators.naukri_locators import JobLocators

logger = logging.getLogger(__name__)

MAX_RETRIES    = 2
RETRY_DELAY_S  = 5


class JobApplicant:
    def __init__(self, page: Page):
        self.page = page

    # ── Public ────────────────────────────────────────────────────────────────

    def apply(self, job: dict) -> bool:
        """Navigate to the job URL and submit an easy-apply application.

        Returns True if application was submitted successfully, False otherwise.
        """
        url = job.get("url", "")
        if not url:
            logger.warning("No URL for job '%s' — cannot apply", job.get("title"))
            return False

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = self._try_apply(job, url)
                if result is not None:
                    return result
            except Exception as e:
                logger.warning(
                    "Apply attempt %d/%d failed for '%s': %s",
                    attempt, MAX_RETRIES, job.get("title"), e,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_S)

        logger.error("All apply attempts exhausted for '%s'", job.get("title"))
        return False

    # ── Private ───────────────────────────────────────────────────────────────

    def _try_apply(self, job: dict, url: str) -> bool | None:
        """
        Returns:
          True   — applied successfully
          False  — already applied or job no longer available
          None   — retriable error occurred
        """
        self.page.goto(url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(2000)

        # Check for captcha before doing anything
        if self._captcha_present():
            logger.error(
                "CAPTCHA detected on '%s' — pausing. Solve manually then resume.",
                job.get("title"),
            )
            input("[ACTION REQUIRED] Solve the CAPTCHA in the browser, then press Enter to continue...")
            return None

        # Already applied?
        if self._already_applied():
            logger.info("Already applied to '%s' — skipping", job.get("title"))
            return False

        # Find and click the apply button (id="apply-button" is stable)
        apply_btn = try_selectors(self.page, JobLocators.APPLY_BUTTON, timeout=5000)
        if not apply_btn:
            logger.warning("Apply button not found for '%s'", job.get("title"))
            return False

        # Click apply — watch for popup (external apply redirect)
        with self.page.context.expect_event("page", timeout=3000) as popup_info:
            apply_btn.click()
        try:
            popup = popup_info.value
            # A new tab opened — this is an external company apply, not Naukri chatbot
            logger.warning(
                "External apply detected for '%s' — new tab opened (%s). Skipping.",
                job.get("title"), popup.url[:80],
            )
            popup.close()
            return False
        except Exception:
            # No popup = good, Naukri kept us on the same page
            pass

        # Guard: if we got navigated away from naukri.com, bail out
        self.page.wait_for_timeout(2000)
        if "naukri.com" not in self.page.url:
            logger.warning(
                "Redirected off Naukri for '%s' (landed on %s) — skipping.",
                job.get("title"), self.page.url[:80],
            )
            self.page.go_back(wait_until="domcontentloaded")
            return False

        # Case 1: chatbot drawer opened → drive the Q&A flow
        try:
            self.page.wait_for_selector(
                "div.chatbot_DrawerContentWrapper", timeout=5000
            )
            applied = JobChatbot(self.page).handle()
            if not applied:
                return None  # Retriable
            logger.info("Applied via chatbot to '%s' @ %s", job.get("title"), job.get("company"))
            return True
        except Exception:
            pass  # Drawer didn't open — check for direct-apply success below

        # Case 2: direct apply — Naukri applied immediately without a chatbot
        if self._direct_apply_success():
            logger.info("Applied directly (no chatbot) to '%s' @ %s", job.get("title"), job.get("company"))
            return True

        # Neither chatbot nor success — something went wrong
        logger.warning("Apply flow unclear for '%s' — no chatbot and no success signal", job.get("title"))
        return None  # Retriable

    def _direct_apply_success(self) -> bool:
        """Check if Naukri applied directly without opening a chatbot drawer."""
        # Give the page a moment to update after the click
        self.page.wait_for_timeout(2000)
        for selector in JobLocators.APPLY_SUCCESS:
            try:
                el = self.page.locator(selector).first
                if el.count() and el.is_visible():
                    return True
            except Exception:
                continue
        # Also treat the apply button turning into "Applied" as success
        for selector in JobLocators.ALREADY_APPLIED:
            try:
                el = self.page.locator(selector).first
                if el.count() and el.is_visible():
                    return True
            except Exception:
                continue
        return False

    def _already_applied(self) -> bool:
        for selector in JobLocators.ALREADY_APPLIED:
            try:
                el = self.page.locator(selector).first
                if el.count() and el.is_visible():
                    return True
            except Exception:
                continue
        return False

    def _captcha_present(self) -> bool:
        captcha_indicators = [
            "iframe[src*='recaptcha']",
            "iframe[src*='captcha']",
            "#captcha",
            ".g-recaptcha",
        ]
        for sel in captcha_indicators:
            try:
                if self.page.locator(sel).count() > 0:
                    return True
            except Exception:
                continue
        return False
