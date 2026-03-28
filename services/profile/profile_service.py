import logging
import os
import random
import time
from pathlib import Path
from playwright.sync_api import Page
from config.settings import NAUKRI_PROFILE_URL
from services.locators.naukri_locators import ProfileLocators
from core.utils import try_selectors

logger = logging.getLogger(__name__)

from services.profile.content_generator import generate_headline_and_summary
_RESUME_DIR      = Path(__file__).parent.parent.parent / "resume_code" / "resume"
_RESUME_GENERATED = _RESUME_DIR / "resume_generated.pdf"
_RESUME_FALLBACK  = Path(__file__).parent.parent.parent / "resume.pdf"
_RESUME_UPLOAD_NAME = "RomeshJain_SoftwareEngineer_Resume.pdf"


class ProfileService:
    """Updates resume headline, profile summary, and resume file on Naukri."""

    def __init__(self, page: Page):
        self.page = page

    # ── Public ────────────────────────────────────────────────────────────────

    def update(self) -> dict:
        """Navigate to profile page and update headline, summary, and resume.

        Not everything is updated every day — randomized to look human:
          - Resume upload:  always (keeps profile active)
          - Headline:       80% chance
          - Summary:        85% chance
          - Each part has a random gap of 4–12 minutes between them

        Returns a dict with before/after values for the daily report.
        """
        self._go_to_profile()
        current_headline, current_summary = self._scrape_current_headline_and_summary()

        # Decide what to update today — equal 33/33/33 split:
        #   0.00–0.33 → both headline and summary
        #   0.33–0.66 → headline only
        #   0.66–1.00 → summary only
        roll = random.random()
        if roll < 0.33:
            do_headline, do_summary = True, True
        elif roll < 0.66:
            do_headline, do_summary = True, False
        else:
            do_headline, do_summary = False, True

        logger.info(
            "Today's profile plan — resume: YES | headline: %s | summary: %s",
            "YES" if do_headline else "SKIP",
            "YES" if do_summary  else "SKIP",
        )

        # Step 1 — always upload resume
        resume_path = self._upload_resume()

        # Generate AI content only for what we'll actually use
        new_headline = current_headline
        new_summary  = current_summary

        if do_headline or do_summary:
            gen_headline, gen_summary = generate_headline_and_summary(
                current_headline, current_summary
            )
            if do_headline:
                new_headline = gen_headline
            if do_summary:
                new_summary = gen_summary

        # Step 2 — update headline (with delay after resume)
        if do_headline:
            self._profile_gap("headline")
            self._update_headline(new_headline)
            self._close_modal_if_present()

        # Step 3 — update summary (with delay after headline or resume)
        if do_summary:
            self._profile_gap("summary")
            self._update_summary(new_summary)
            self._close_modal_if_present()

        return {
            "prev_headline": current_headline,
            "new_headline":  new_headline,
            "prev_summary":  current_summary,
            "new_summary":   new_summary,
            "resume_path":   resume_path,
        }

    def _profile_gap(self, next_step: str):
        """Random human pause between profile update steps (4–12 minutes)."""
        delay = random.uniform(4 * 60, 12 * 60)
        logger.info(
            "Waiting %.1f min before updating %s (looks human)",
            delay / 60, next_step,
        )
        time.sleep(delay)

    # ── Private ───────────────────────────────────────────────────────────────

    def _go_to_profile(self):
        if not self.page.url.startswith(NAUKRI_PROFILE_URL):
            self.page.goto(NAUKRI_PROFILE_URL, wait_until="domcontentloaded")
        self.page.wait_for_timeout(3000)
        logger.info("On profile page — widgets loaded")

    def _scrape_current_headline_and_summary(self) -> tuple[str, str]:
        """Read current headline and summary by opening each edit form, reading the
        textarea value, then cancelling — guarantees exact live content with no
        dependency on read-only display selectors."""
        headline = self._read_field_via_edit_form(
            edit_trigger_selectors=ProfileLocators.HEADLINE_EDIT,
            form_selector=ProfileLocators.HEADLINE_FORM,
            textarea_selector=ProfileLocators.HEADLINE_INPUT[0],
            label="headline",
        )
        summary = self._read_field_via_edit_form(
            edit_trigger_selectors=ProfileLocators.SUMMARY_EDIT,
            form_selector=ProfileLocators.SUMMARY_FORM,
            textarea_selector=ProfileLocators.SUMMARY_INPUT[0],
            label="summary",
        )
        return headline, summary

    def _read_field_via_edit_form(
        self,
        edit_trigger_selectors: list,
        form_selector: str,
        textarea_selector: str,
        label: str,
    ) -> str:
        """Open an edit form, read the textarea value, cancel, return the value."""
        try:
            # Scroll down incrementally until the edit trigger is visible
            edit_btn = None
            for _ in range(20):
                edit_btn = try_selectors(self.page, edit_trigger_selectors, timeout=1000)
                if edit_btn:
                    break
                self.page.evaluate("window.scrollBy(0, 400)")
                self.page.wait_for_timeout(300)
            if not edit_btn:
                logger.warning("Could not find edit trigger for %s — skipping scrape", label)
                return ""
            edit_btn.click()
            self.page.wait_for_selector(form_selector, timeout=5000)
            value = self.page.locator(textarea_selector).input_value()
            # Cancel the form without saving
            self.page.keyboard.press("Escape")
            try:
                self.page.wait_for_selector(form_selector, state="hidden", timeout=4000)
            except Exception:
                pass
            self._close_modal_if_present()
            logger.info("Scraped current %s (%d chars)", label, len(value))
            return value.strip()
        except Exception as exc:
            logger.warning("Could not scrape current %s: %s", label, exc)
            return ""

    def _close_modal_if_present(self):
        """Dismiss the crossLayer confirmation modal that appears after saves."""
        try:
            self.page.locator(".crossLayer:visible").first.click(timeout=3000)
            self.page.wait_for_timeout(800)
            logger.debug("Closed post-save modal")
        except Exception:
            pass

    def _update_headline(self, headline: str):
        logger.info("Updating resume headline...")

        edit_btn = try_selectors(self.page, ProfileLocators.HEADLINE_EDIT, timeout=5000)
        if not edit_btn:
            raise RuntimeError("Resume headline edit trigger not found")
        edit_btn.click()

        self.page.wait_for_selector(ProfileLocators.HEADLINE_FORM, timeout=5000)

        field = try_selectors(self.page, ProfileLocators.HEADLINE_INPUT, timeout=5000)
        if not field:
            raise RuntimeError("Resume headline textarea not found")
        field.fill(headline)

        save = try_selectors(self.page, ProfileLocators.HEADLINE_SAVE, timeout=5000)
        if not save:
            raise RuntimeError("Resume headline save button not found")
        save.click()

        self.page.wait_for_selector(
            ProfileLocators.HEADLINE_FORM, state="hidden", timeout=8000
        )
        logger.info("Resume headline updated")

    def _update_summary(self, summary: str):
        logger.info("Updating profile summary...")

        # Scroll down in steps until the summary widget is visible
        edit_btn = (
            self.page.locator(".widgetHead")
            .filter(has_text="Profile summary")
            .locator("span.edit.icon")
        )
        for _ in range(20):
            if edit_btn.is_visible():
                break
            self.page.evaluate("window.scrollBy(0, 400)")
            self.page.wait_for_timeout(400)
        else:
            raise RuntimeError("Profile summary widget not found after scrolling")

        edit_btn.click()

        self.page.wait_for_selector(ProfileLocators.SUMMARY_FORM, timeout=5000)

        field = try_selectors(self.page, ProfileLocators.SUMMARY_INPUT, timeout=5000)
        if not field:
            raise RuntimeError("Profile summary textarea not found")
        field.fill(summary)

        save = try_selectors(self.page, ProfileLocators.SUMMARY_SAVE, timeout=5000)
        if not save:
            raise RuntimeError("Profile summary save button not found")
        save.click()

        self.page.wait_for_selector(
            ProfileLocators.SUMMARY_FORM, state="hidden", timeout=8000
        )
        logger.info("Profile summary updated")

    def _upload_resume(self) -> str | None:
        """Upload resume to Naukri and return the local path saved for email attachment."""
        logger.info("Preparing resume for upload...")

        # Try to generate a fresh AI resume; fall back to resume.pdf on any failure
        generated = False
        try:
            from resume_code.generate_resume import generate_resume
            generate_resume()
            generated = True
            logger.info("AI resume generated successfully")
        except Exception as exc:
            logger.warning("Resume generation failed (%s) — falling back to resume.pdf", exc)

        if generated and _RESUME_GENERATED.is_file():
            resume_path = _RESUME_GENERATED
        else:
            resume_path = _RESUME_FALLBACK
            logger.info("Using fallback resume: %s", resume_path)

        if not resume_path.is_file():
            raise FileNotFoundError("Resume file not found at: %s" % resume_path)

        self.page.evaluate("window.scrollTo(0, 0)")
        self.page.wait_for_timeout(1000)

        upload_input = try_selectors(self.page, ProfileLocators.RESUME_UPLOAD, timeout=5000)
        if not upload_input:
            raise RuntimeError("Resume upload input not found")

        with open(resume_path, "rb") as f:
            upload_input.set_input_files({
                "name": _RESUME_UPLOAD_NAME,
                "mimeType": "application/pdf",
                "buffer": f.read(),
            })

        # Confirm the "replace resume" dialog if it appears
        confirm = try_selectors(self.page, ProfileLocators.RESUME_CONFIRM, timeout=5000)
        if confirm:
            confirm.click()
            logger.debug("Confirmed resume replacement")

        self.page.wait_for_timeout(4000)
        logger.info("Resume uploaded successfully — keeping file at %s for email attachment", resume_path)

        # Return the path as-is — deletion happens in the scheduler after the email is sent
        return str(resume_path)
