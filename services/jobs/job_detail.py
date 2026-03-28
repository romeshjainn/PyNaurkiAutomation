"""
Fetches full job details from individual Naukri job pages.

Responsibilities:
  - Navigate to each job's detail URL
  - Extract: full description, required skills, easy-apply button presence
  - Add realistic dwell time before leaving (looks human)
  - Update the job dict in-place with the enriched data
"""

import logging
import random
import time

from playwright.sync_api import Page

from services.locators.naukri_locators import JobLocators

logger = logging.getLogger(__name__)

# Seconds to stay on the page before moving on (simulates reading)
DWELL_MIN = 5
DWELL_MAX = 15


class JobDetailFetcher:
    def __init__(self, page: Page):
        self.page = page

    # ── Public ────────────────────────────────────────────────────────────────

    def enrich(self, job: dict) -> dict:
        """Navigate to the job detail page and fill in description + skills.

        Mutates and returns the same job dict.
        """
        url = job.get("url", "")
        if not url:
            logger.warning("No URL for job '%s' — skipping detail fetch", job.get("title"))
            return job

        try:
            self.page.goto(url, wait_until="domcontentloaded")
            self.page.wait_for_timeout(random.randint(1500, 3000))

            job["description"] = self._get_description()
            job["skills"]      = self._get_skills()
            job["easy_apply"]  = self._has_easy_apply() or job.get("easy_apply", False)

            dwell = random.uniform(DWELL_MIN, DWELL_MAX)
            logger.debug("Dwell %.1fs on '%s'", dwell, job["title"])
            time.sleep(dwell)

        except Exception as e:
            logger.warning("Detail fetch failed for '%s': %s", job.get("title"), e)

        return job

    def enrich_batch(self, jobs: list[dict]) -> list[dict]:
        """Enrich a list of jobs. Returns the same list with details filled in."""
        for i, job in enumerate(jobs):
            logger.info("Fetching detail %d/%d: %s", i + 1, len(jobs), job.get("title"))
            self.enrich(job)
        return jobs

    # ── Private ───────────────────────────────────────────────────────────────

    def _get_description(self) -> str:
        for selector in JobLocators.DETAIL_DESCRIPTION:
            try:
                el = self.page.locator(selector).first
                if el.count():
                    return el.inner_text().strip()
            except Exception:
                continue
        return ""

    def _get_skills(self) -> list[str]:
        for selector in JobLocators.DETAIL_SKILLS:
            try:
                els = self.page.locator(selector)
                if els.count():
                    return [
                        els.nth(i).inner_text().strip()
                        for i in range(els.count())
                        if els.nth(i).inner_text().strip()
                    ]
            except Exception:
                continue
        return []

    def _has_easy_apply(self) -> bool:
        for selector in JobLocators.DETAIL_EASY_APPLY:
            try:
                btn = self.page.locator(selector).first
                if btn.count() and btn.is_visible():
                    return True
            except Exception:
                continue
        return False
