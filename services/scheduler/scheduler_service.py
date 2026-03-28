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
import shutil
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from services.browser.browser_service import BrowserService
from services.auth.login_service import LoginService
from services.jobs.job_session import JobSession
from services.jobs.job_store import JobStore
from services.notifier.email_service import EmailService
from services.profile.profile_service import ProfileService

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


def _cleanup_resume(resume_path: str | None):
    """Delete the generated resume file and its output folder after email is sent."""
    _RESUME_DIR = Path("resume_code") / "resume"
    try:
        if _RESUME_DIR.exists():
            shutil.rmtree(_RESUME_DIR)
            logger.info("Deleted resume output folder: %s", _RESUME_DIR)
    except Exception as e:
        logger.warning("Could not delete resume folder: %s", e)

    if resume_path:
        try:
            p = Path(resume_path)
            if p.exists():
                p.unlink()
                logger.info("Deleted resume file: %s", resume_path)
        except Exception as e:
            logger.warning("Could not delete resume file %s: %s", resume_path, e)


def _run_session(session_type: str, daily_report: dict) -> list[str]:
    """Launch browser, log in, run profile update (morning only) + job session.

    Returns a list of error strings encountered during this session.
    """
    errors: list[str] = []
    email_svc = EmailService()
    browser   = BrowserService()
    page      = browser.launch()
    session   = JobSession(page)
    try:
        LoginService(page).ensure_logged_in()

        # Morning session also updates the profile and captures before/after data
        if session_type == "morning":
            try:
                profile_data = ProfileService(page).update()
                daily_report.update(profile_data)
            except Exception as e:
                err = f"Profile update failed: {traceback.format_exc()}"
                logger.error(err)
                errors.append(err)
                email_svc.send_error_alert("Profile update failed", traceback.format_exc())

        if session_type == "morning":
            session.run_morning_session()
        else:
            session.run_afternoon_session()

    except Exception as e:
        err = f"{session_type.capitalize()} session crashed: {traceback.format_exc()}"
        logger.error(err)
        errors.append(err)
        email_svc.send_error_alert(f"{session_type.capitalize()} session crashed", traceback.format_exc())
    finally:
        session.close()
        browser.close()

    return errors


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

        today        = datetime.now().date().isoformat()
        daily_report = {"date": today, "errors": []}
        store        = JobStore()
        email_svc    = EmailService()

        # ── Morning session ────────────────────────────────────────────────────
        _wait_until(morning_time)
        logger.info("Starting morning session")
        errs = _run_session("morning", daily_report)
        daily_report["errors"].extend(errs)

        # ── Afternoon session ──────────────────────────────────────────────────
        _wait_until(afternoon_time)
        logger.info("Starting afternoon session")
        errs = _run_session("afternoon", daily_report)
        daily_report["errors"].extend(errs)

        # ── End-of-day report + cleanup ────────────────────────────────────────
        try:
            daily_report["applied_jobs"] = store.applied_today_details()
            email_svc.send_daily_report(daily_report)
            logger.info(
                "Daily report sent — %d jobs applied",
                len(daily_report["applied_jobs"]),
            )
        except Exception as e:
            logger.error("Failed to send daily report: %s", e)
        finally:
            # Delete resume files AFTER email is sent — generated folder + any fallback copy
            _cleanup_resume(daily_report.get("resume_path"))

            # Purge non-applied rows — keep only applied history for dedup
            try:
                store.purge_non_applied()
            except Exception as e:
                logger.error("Purge failed: %s", e)
            store.close()

        # Sleep a short buffer before the next day's scheduling loop
        time.sleep(60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    run_scheduler()
