import logging
import os
from playwright.sync_api import Page
from config.settings import NAUKRI_PROFILE_URL
from services.locators.naukri_locators import ProfileLocators
from core.utils import try_selectors

logger = logging.getLogger(__name__)

# ── Hardcoded test content (replace with profile.json values later) ───────────
_TEST_HEADLINE = "Software Engineer | Python | Cloud | Automation"
_TEST_SUMMARY = (
    "Experienced software engineer with a strong background in Python development, "
    "cloud infrastructure, and automation. Passionate about building scalable, "
    "maintainable systems and delivering high-quality software solutions."
)
_RESUME_FILENAME = "resume.pdf"
_RESUME_UPLOAD_NAME = "RomeshJain_SoftwareEngineer_Resume.pdf"


class ProfileService:
    """Updates resume headline, profile summary, and resume file on Naukri."""

    def __init__(self, page: Page):
        self.page = page

    # ── Public ────────────────────────────────────────────────────────────────

    def update(self):
        """Navigate to profile page and update headline, summary, and resume."""
        self._go_to_profile()
        self._upload_resume(_RESUME_FILENAME)
        self._update_headline(_TEST_HEADLINE)
        self._close_modal_if_present()
        self._update_summary(_TEST_SUMMARY)
        self._close_modal_if_present()

    # ── Private ───────────────────────────────────────────────────────────────

    def _go_to_profile(self):
        if not self.page.url.startswith(NAUKRI_PROFILE_URL):
            self.page.goto(NAUKRI_PROFILE_URL, wait_until="domcontentloaded")
        self.page.wait_for_timeout(3000)
        logger.info("On profile page — widgets loaded")

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

    def _upload_resume(self, filename: str):
        logger.info("Uploading resume: %s", filename)

        resume_path = os.path.join(os.getcwd(), filename)
        if not os.path.isfile(resume_path):
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
        logger.info("Resume uploaded successfully")
