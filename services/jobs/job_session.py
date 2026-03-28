"""
Job session orchestrator — the single file that runs the full apply pipeline.

All human simulation logic lives here:
  - Randomized session start delay
  - Decoy browsing before applying
  - Per-application inter-delays (3–8 min)
  - Random scroll/hover dwell on job cards

Two entry points:
  run_morning_session()   — best-scored jobs, 4–6 applications
  run_afternoon_session() — fresh jobs only (≤6h), 3–5 applications

To add or tune human simulation: edit only this file.
"""

import logging
import random
import time

from playwright.sync_api import Page

from services.jobs.job_applicant import JobApplicant
from services.jobs.job_detail import JobDetailFetcher
from services.jobs.job_filters import FILTERS, passes_must_have
from services.jobs.job_scorer import JobScorer
from services.jobs.job_scraper import JobScraper
from services.jobs.job_store import JobStore

logger = logging.getLogger(__name__)

# ── Test mode ──────────────────────────────────────────────────────────────────
# Set to True to run a quick 2-job test with all delays stripped out.
TEST_MODE = True

# ── Session limits ─────────────────────────────────────────────────────────────
MORNING_TARGET   = (4, 6)   # (min, max) applications
AFTERNOON_TARGET = (3, 5)

# ── Human simulation knobs ─────────────────────────────────────────────────────
INTER_APP_DELAY_MIN   = 3 * 60    # 3 minutes between applications (seconds)
INTER_APP_DELAY_MAX   = 8 * 60    # 8 minutes between applications (seconds)
DECOY_JOBS_COUNT      = (2, 3)    # browse this many jobs without applying
DECOY_DWELL_MIN       = 8         # seconds to "read" a decoy job
DECOY_DWELL_MAX       = 20
SCROLL_PAUSE_MIN      = 1.5       # seconds between scroll steps
SCROLL_PAUSE_MAX      = 3.5


class JobSession:
    def __init__(self, page: Page):
        self.page      = page
        self.store     = JobStore()
        self.scraper   = JobScraper(page)
        self.fetcher   = JobDetailFetcher(page)
        self.scorer    = JobScorer()
        self.applicant = JobApplicant(page)

    # ── Public entry points ───────────────────────────────────────────────────

    def run_morning_session(self):
        """Morning session: apply to top-scored jobs. Target 4–6 applications."""
        logger.info("=== MORNING SESSION START%s ===", " [TEST MODE]" if TEST_MODE else "")
        if not TEST_MODE:
            self._decoy_browse()
        target = (2, 2) if TEST_MODE else MORNING_TARGET
        self._run_session(afternoon=False, target=target)
        logger.info("=== MORNING SESSION END ===")

    def run_afternoon_session(self):
        """Afternoon session: fresh jobs only (<=6h). Target 3-5 applications."""
        logger.info("=== AFTERNOON SESSION START%s ===", " [TEST MODE]" if TEST_MODE else "")
        if not TEST_MODE:
            self._decoy_browse()
        target = (2, 2) if TEST_MODE else AFTERNOON_TARGET
        self._run_session(afternoon=True, target=target)
        logger.info("=== AFTERNOON SESSION END ===")

    def close(self):
        """Call once after all sessions are done."""
        self.store.close()

    # ── Core pipeline ──────────────────────────────────────────────────────────

    def _run_session(self, afternoon: bool, target: tuple[int, int]):
        already_applied_today = self.store.applied_today_ids()
        max_applications      = random.randint(*target)

        logger.info(
            "Session target: %d applications | Already applied today: %d",
            max_applications, len(already_applied_today),
        )

        # Step 1: Scrape + static filter
        candidates = self.scraper.scrape_all_targets(afternoon=afternoon)

        # Step 2: Dedup — skip jobs already seen or applied to
        fresh = [j for j in candidates if j["job_id"] not in already_applied_today]
        logger.info("%d fresh candidates after dedup", len(fresh))

        if not fresh:
            logger.info("No fresh candidates — session ends early")
            return

        # Step 3: Visit each detail page — check easy apply FIRST, then get description
        # Jobs without easy apply are skipped immediately (no LLM call wasted)
        fresh = self.fetcher.enrich_batch(fresh)

        easy_apply_jobs = [j for j in fresh if j.get("easy_apply", False)]
        skipped = len(fresh) - len(easy_apply_jobs)
        logger.info("%d/%d jobs have easy apply (skipped %d without it)",
                    len(easy_apply_jobs), len(fresh), skipped)

        # Step 4: Must-have keyword check on title + full description
        easy_apply_jobs = [
            j for j in easy_apply_jobs
            if passes_must_have(j["title"], j.get("description", ""), j["must_have"])[0]
        ]
        logger.info("%d candidates pass must-have keyword check", len(easy_apply_jobs))

        # Step 5: Score only easy-apply + must-have jobs with LLM
        scored = self.scorer.score_batch(easy_apply_jobs)

        # Step 6: Persist scores to DB
        for job in scored:
            self.store.insert_new(job)
            self.store.update_scores(
                job["job_id"],
                job["llm_score"],
                job["structural_score"],
                job["combined_score"],
            )

        # Step 7: Apply queue — jobs that scored above threshold
        apply_queue = [
            j for j in scored
            if j.get("combined_score", 0) >= FILTERS["APPLY_MIN_SCORE"]
        ]

        logger.info("%d jobs ready to apply (score >= %d, easy_apply=True)",
                    len(apply_queue), FILTERS["APPLY_MIN_SCORE"])

        applied_count = 0
        for job in apply_queue:
            if applied_count >= max_applications:
                break

            logger.info(
                "[%d/%d] Applying to '%s' @ %s (score=%.1f)",
                applied_count + 1, max_applications,
                job["title"], job["company"], job["combined_score"],
            )

            success = self.applicant.apply(job)

            if success:
                self.store.mark_applied(job["job_id"])
                applied_count += 1
                if applied_count < max_applications:
                    self._inter_application_delay()
            else:
                self.store.mark_skipped(job["job_id"], "apply_failed")

        logger.info("Session complete — applied to %d jobs", applied_count)

    # ── Human simulation ───────────────────────────────────────────────────────

    def _decoy_browse(self):
        """Browse 2–3 random job pages without applying. Looks human."""
        count = random.randint(*DECOY_JOBS_COUNT)
        logger.debug("Decoy browsing %d jobs", count)

        # Use the first target URL as the decoy search page
        from services.jobs.job_filters import JOB_TARGETS
        decoy_url = random.choice(JOB_TARGETS)["url"]

        self.page.goto(decoy_url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(random.randint(2000, 4000))
        self._human_scroll()

        from services.locators.naukri_locators import JobLocators
        for selector in JobLocators.JOB_CARDS:
            cards = self.page.locator(selector)
            if cards.count() >= count:
                indices = random.sample(range(cards.count()), min(count, cards.count()))
                for idx in indices:
                    try:
                        link = cards.nth(idx).locator(JobLocators.CARD_TITLE).first
                        if link.count():
                            href = link.get_attribute("href") or ""
                            if href:
                                full = f"https://www.naukri.com{href}" if href.startswith("/") else href
                                self.page.goto(full, wait_until="domcontentloaded")
                                dwell = random.uniform(DECOY_DWELL_MIN, DECOY_DWELL_MAX)
                                logger.debug("Decoy dwell %.1fs", dwell)
                                self._human_scroll()
                                time.sleep(dwell)
                                self.page.go_back(wait_until="domcontentloaded")
                                self.page.wait_for_timeout(random.randint(1500, 3000))
                    except Exception as e:
                        logger.debug("Decoy browse error: %s", e)
                break

    def _inter_application_delay(self):
        """Wait 3–8 minutes between applications with slight variance."""
        if TEST_MODE:
            logger.info("TEST MODE — skipping inter-application delay")
            return
        delay = random.uniform(INTER_APP_DELAY_MIN, INTER_APP_DELAY_MAX)
        # Add gaussian jitter (±30 seconds)
        jitter = random.gauss(0, 30)
        delay  = max(60, delay + jitter)   # never less than 1 minute
        logger.info("Inter-application delay: %.0f seconds (%.1f min)", delay, delay / 60)
        time.sleep(delay)

    def _human_scroll(self):
        """Scroll down the page in irregular steps, occasionally back up."""
        steps = random.randint(3, 7)
        for i in range(steps):
            # Random scroll amount — not always the same direction
            direction = 1 if random.random() > 0.2 else -1   # 20% chance to scroll up
            amount    = random.randint(250, 600) * direction
            self.page.evaluate(f"window.scrollBy(0, {amount})")
            pause = random.uniform(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX)
            time.sleep(pause)
