"""
Test full pipeline: scrape → filter → score → apply.
TEST_MODE=True strips all delays and caps at 2 applications.
WARNING: submits real applications on Naukri.
Run: python test_apply.py
"""
import logging, sys
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stdout)

import services.jobs.job_session as job_session_module
job_session_module.TEST_MODE = True  # no delays, 2 jobs max

from services.browser.browser_service import BrowserService
from services.auth.login_service import LoginService
from services.jobs.job_session import JobSession

browser = BrowserService()
page = browser.launch()
session = JobSession(page)
try:
    LoginService(page).ensure_logged_in()
    session.run_morning_session()
finally:
    session.close()
    browser.close()
