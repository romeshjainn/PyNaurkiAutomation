"""
Scrapes Naukri job listing pages.

Responsibilities:
  - Navigate to a job target URL
  - Sort results by date (newest first) — mandatory on every page load
  - Extract raw job data from each card
  - Run static pre-filter (title blocklist, recency, applicants, salary, experience)
  - Paginate until TARGET_FILTERED jobs collected or MAX_PAGES reached
  - Afternoon mode: applies an extra ≤6h recency constraint
"""

import logging
import random
import time

from playwright.sync_api import Page

from core.utils import try_selectors
from services.jobs.job_filters import (
    FILTERS,
    JOB_TARGETS,
    passes_pre_filter,
    passes_title_filter,
    parse_applicants,
    parse_experience,
    parse_posted_hours,
    parse_salary_lpa,
)
from services.locators.naukri_locators import JobLocators

logger = logging.getLogger(__name__)

TARGET_FILTERED = 15   # Stop paginating once we have this many passing jobs
MAX_PAGES       = FILTERS["MAX_PAGES_PER_TYPE"]
AFTERNOON_MAX_H = 6    # Afternoon session: only jobs posted within last 6 hours


class JobScraper:
    def __init__(self, page: Page):
        self.page = page

    # ── Public ────────────────────────────────────────────────────────────────

    def scrape_all_targets(self, afternoon: bool = False) -> list[dict]:
        """Scrape every JOB_TARGET and return the combined filtered list."""
        all_jobs: list[dict] = []
        seen_ids: set[str] = set()

        for target in JOB_TARGETS:
            jobs = self.scrape_target(target, afternoon=afternoon)
            for job in jobs:
                if job["job_id"] not in seen_ids:
                    seen_ids.add(job["job_id"])
                    all_jobs.append(job)

        logger.info("Total unique filtered jobs across all targets: %d", len(all_jobs))
        return all_jobs

    def scrape_target(self, target: dict, afternoon: bool = False) -> list[dict]:
        """Scrape one job target URL with pagination via Next button.

        Sorts by Date once on page 1, then clicks Next to preserve sort state.
        URL-based pagination would reset sort on every page load.
        """
        from services.jobs.job_session import TEST_MODE

        filtered: list[dict] = []
        empty_pages = 0

        # ── Page 1: navigate + sort ───────────────────────────────────────────
        logger.info("[%s] Navigating to search URL", target["type"])
        self.page.goto(target["url"], wait_until="domcontentloaded")
        self.page.wait_for_timeout(random.randint(800, 1500) if TEST_MODE else random.randint(2500, 4000))
        self._sort_by_date()   # Sort once — Next-button navigation preserves it

        for page_num in range(1, MAX_PAGES + 1):
            logger.info("[%s] Scraping page %d (url=%s)", target["type"], page_num, self.page.url[:80])

            raw_jobs = self._extract_cards(target)

            if not raw_jobs:
                empty_pages += 1
                logger.info("[%s] Page %d: no cards found", target["type"], page_num)
                if empty_pages >= FILTERS["DEAD_PAGES_LIMIT"]:
                    break
                # Try to continue to next page anyway
            else:
                empty_pages = 0
                page_passed = 0

                for job in raw_jobs:
                    passes, reason = passes_pre_filter(job)
                    if not passes:
                        logger.debug("SKIP '%s' — %s", job.get("title", "?"), reason)
                        continue

                    if afternoon and job.get("posted_hours") is not None:
                        if job["posted_hours"] > AFTERNOON_MAX_H:
                            logger.debug("Afternoon SKIP '%s' — %.1fh", job.get("title"), job["posted_hours"])
                            continue

                    filtered.append(job)
                    page_passed += 1

                logger.info("[%s] Page %d: %d/%d passed | total: %d",
                            target["type"], page_num, page_passed, len(raw_jobs), len(filtered))

            if len(filtered) >= TARGET_FILTERED:
                logger.info("[%s] Hit target (%d) — stopping", target["type"], TARGET_FILTERED)
                break

            if page_num >= MAX_PAGES:
                break

            # ── Navigate to next page ─────────────────────────────────────────
            delay = 1 if TEST_MODE else random.uniform(8, 15)
            logger.debug("Pagination delay %.1fs", delay)
            time.sleep(delay)

            next_btn = try_selectors(self.page, JobLocators.NEXT_PAGE, timeout=3000)
            if next_btn:
                # Preferred: click Next button — keeps sort state
                next_btn.click()
                try:
                    self.page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    self.page.wait_for_timeout(2000)
            else:
                # Fallback: URL-based navigation — re-sorts on each page
                logger.debug("[%s] Next button not found — falling back to URL pagination", target["type"])
                import re as _re
                current = self.page.url
                current = _re.sub(r"[&?]pageNo=\d+", "", current)
                sep = "&" if "?" in current else "?"
                next_url = f"{current}{sep}pageNo={page_num + 1}"
                self.page.goto(next_url, wait_until="domcontentloaded")
                self.page.wait_for_timeout(random.randint(800, 1500) if TEST_MODE else random.randint(2000, 3500))
                self._sort_by_date()   # Re-sort since URL navigation resets it

        return filtered

    # ── Private ───────────────────────────────────────────────────────────────

    def _sort_by_date(self):
        """Two-step sort: open dropdown → click Date option.

        Also verifies the active label changed to 'Date' before continuing.
        Must run on every page load — Naukri resets sort on pagination.
        """
        try:
            # Check if already sorted by Date
            active_label = self.page.locator(JobLocators.SORT_ACTIVE_LABEL).first
            if active_label.count() and active_label.inner_text().strip().lower() == "date":
                logger.debug("Already sorted by Date — skipping")
                return

            # Step 1: open the dropdown
            trigger = try_selectors(self.page, JobLocators.SORT_DROPDOWN_TRIGGER, timeout=5000)
            if not trigger:
                logger.warning("Sort dropdown trigger not found — results may not be date-sorted")
                return
            trigger.click()
            self.page.wait_for_timeout(500)

            # Step 2: click the Date option
            date_opt = try_selectors(self.page, JobLocators.SORT_DATE_OPTION, timeout=3000)
            if not date_opt:
                logger.warning("Date sort option not found — results may not be date-sorted")
                return
            date_opt.click()

            # Wait for page to reload with date-sorted results
            try:
                self.page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                self.page.wait_for_timeout(2500)

            logger.debug("Sorted by Date")
        except Exception as e:
            logger.warning("Sort-by-date failed: %s", e)

    def _extract_cards(self, target: dict) -> list[dict]:
        # Try each card selector until one finds results
        cards = None
        for selector in JobLocators.JOB_CARDS:
            locator = self.page.locator(selector)
            if locator.count() > 0:
                cards = locator
                break

        if cards is None:
            logger.warning("No job cards found on page")
            return []

        jobs = []
        for i in range(cards.count()):
            try:
                job = self._parse_card(cards.nth(i), target)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.debug("Card %d parse error: %s", i, e)

        return jobs

    def _parse_card(self, card, target: dict) -> dict | None:
        # Job ID — directly on the wrapper via data-job-id attribute
        job_id = card.get_attribute("data-job-id") or ""

        # Title + URL
        title_el = card.locator(JobLocators.CARD_TITLE).first
        if not title_el.count():
            return None
        title   = title_el.inner_text().strip()
        job_url = title_el.get_attribute("href") or ""

        if not title:
            return None

        # Fallback job_id if data attribute was missing
        if not job_id:
            job_id = self._extract_job_id(job_url)
        if not job_id:
            import hashlib
            company_raw = self._safe_text(card, JobLocators.CARD_COMPANY)
            job_id = hashlib.md5(f"{title}|{company_raw}".encode()).hexdigest()[:16]

        logger.debug("Card: id=%s | %s", job_id, title[:60])

        company      = self._safe_text(card, JobLocators.CARD_COMPANY)
        salary_raw   = self._safe_text(card, JobLocators.CARD_SALARY)
        exp_raw      = self._safe_text(card, JobLocators.CARD_EXP)
        posted_raw   = self._safe_text(card, JobLocators.CARD_POSTED)
        applicants_raw = self._safe_text(card, JobLocators.CARD_APPLICANTS)

        exp_min, exp_max = parse_experience(exp_raw)
        posted_hours     = parse_posted_hours(posted_raw)
        applicants_count = parse_applicants(applicants_raw)
        salary_lpa_min   = parse_salary_lpa(salary_raw)

        easy_apply = False   # determined on the detail page, not the list card

        full_url = (
            f"https://www.naukri.com{job_url}"
            if job_url.startswith("/")
            else job_url
        )

        return {
            "job_id":          job_id,
            "title":           title,
            "company":         company,
            "url":             full_url,
            "salary_raw":      salary_raw,
            "salary_lpa_min":  salary_lpa_min,
            "exp_raw":         exp_raw,
            "exp_min":         exp_min,
            "exp_max":         exp_max,
            "posted_raw":      posted_raw,
            "posted_hours":    posted_hours,
            "applicants_raw":  applicants_raw,
            "applicants_count": applicants_count,
            "easy_apply":      easy_apply,
            "target_type":     target["type"],
            "must_have":       target["mustHave"],
            "keywords":        target["keywords"],
            # Detail fields — filled later by JobDetailFetcher
            "description":     "",
            "skills":          [],
        }

    @staticmethod
    def _extract_job_id(url: str) -> str:
        """Extract numeric Naukri job ID from a job URL."""
        if not url:
            return ""
        # Naukri URLs end with -XXXXXXXXXX.htm or ?jobId=XXXXXXXXXX
        import re
        m = re.search(r"[/-](\d{8,12})(?:[.?]|$)", url)
        return m.group(1) if m else url.rstrip("/").split("/")[-1].split("?")[0]

    @staticmethod
    def _safe_text(element, selector: str) -> str:
        try:
            loc = element.locator(selector).first
            if loc.count():
                return loc.inner_text().strip()
        except Exception:
            pass
        return ""
