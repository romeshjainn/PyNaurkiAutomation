"""Test profile update (resume upload + headline + summary). Run: python test_profile.py"""
import logging, sys
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stdout)

from services.browser.browser_service import BrowserService
from services.auth.login_service import LoginService
from services.profile.profile_service import ProfileService

browser = BrowserService()
page = browser.launch()
try:
    LoginService(page).ensure_logged_in()
    result = ProfileService(page).update(force_all=True, skip_gaps=True)
    print("\n--- Result ---")
    print("Headline before:", result.get("prev_headline"))
    print("Headline after :", result.get("new_headline"))
    print("Summary before :", result.get("prev_summary", "")[:100])
    print("Summary after  :", result.get("new_summary", "")[:100])
    print("Resume         :", result.get("resume_path"))
finally:
    browser.close()
