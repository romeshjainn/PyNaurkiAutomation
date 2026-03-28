"""
Daily two-session scheduler with Gaussian-randomized run windows.

Morning  : 7:00 AM – 11:00 AM  (applies to top-scored jobs)
Afternoon: 2:00 PM –  5:00 PM  (fresh jobs only, ≤6 hours old)

Each window is sampled from a Gaussian distribution centred at the midpoint
so runs feel natural rather than evenly spread or biased to one end.

Usage:
    python -m services.scheduler.scheduler_service
"""

import logging
import random
import time
from datetime import datetime, timedelta

from services.browser.browser_service import BrowserService
from services.auth.login_service import LoginService
from services.jobs.job_session import JobSession

logger = logging.getLogger(__name__)

# ── Window definitions (24h clock, minutes from midnight) ─────────────────────
MORNING_START   = 7 * 60        # 07:00
MORNING_END     = 11 * 60       # 11:00
AFTERNOON_START = 14 * 60       # 14:00
AFTERNOON_END   = 17 * 60       # 17:00

# Gaussian std-dev as a fraction of the window width
GAUSSIAN_SIGMA_FRACTION = 0.25


def _random_minute_in_window(start_min: int, end_min: int) -> int:
    """Return a random minute-of-day within [start_min, end_min] using a
    Gaussian distribution centred at the midpoint."""
    centre = (start_min + end_min) / 2
    sigma  = (end_min - start_min) * GAUSSIAN_SIGMA_FRACTION
    while True:
        sample = random.gauss(centre, sigma)
        if start_min <= sample <= end_min:
            return int(sample)


def _next_run_time(start_min: int, end_min: int) -> datetime:
    """Return the next datetime to run within the given window (today or tomorrow)."""
    now         = datetime.now()
    target_min  = _random_minute_in_window(start_min, end_min)
    target_time = now.replace(hour=target_min // 60, minute=target_min % 60,
                               second=0, microsecond=0)

    if target_time <= now:
        target_time += timedelta(days=1)   # window already passed today — schedule tomorrow

    return target_time


def _wait_until(target: datetime):
    """Block until target datetime, logging a countdown every 30 minutes."""
    while True:
        now     = datetime.now()
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return
        if remaining > 60:
            logger.info(
                "Next run at %s — %.0f minutes remaining",
                target.strftime("%H:%M"), remaining / 60,
            )
            time.sleep(min(remaining - 30, 30 * 60))
        else:
            time.sleep(remaining)
            return


def _run_session(session_type: str):
    """Launch browser, log in, run the requested session, then close."""
    browser = BrowserService()
    page    = browser.launch()
    session = JobSession(page)
    try:
        LoginService(page).ensure_logged_in()
        if session_type == "morning":
            session.run_morning_session()
        else:
            session.run_afternoon_session()
    except Exception as e:
        logger.error("Session '%s' failed: %s", session_type, e, exc_info=True)
    finally:
        session.close()
        browser.close()


def run_scheduler():
    """Main loop — schedules and runs morning + afternoon sessions indefinitely."""
    logger.info("Scheduler started")

    while True:
        morning_time   = _next_run_time(MORNING_START,   MORNING_END)
        afternoon_time = _next_run_time(AFTERNOON_START, AFTERNOON_END)

        logger.info(
            "Scheduled — morning: %s | afternoon: %s",
            morning_time.strftime("%Y-%m-%d %H:%M"),
            afternoon_time.strftime("%Y-%m-%d %H:%M"),
        )

        _wait_until(morning_time)
        logger.info("Starting morning session")
        _run_session("morning")

        _wait_until(afternoon_time)
        logger.info("Starting afternoon session")
        _run_session("afternoon")

        # Sleep a short buffer before the next day's scheduling loop
        time.sleep(60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    run_scheduler()
