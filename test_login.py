"""Test login. Run: python test_login.py"""
import logging, sys
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stdout)

from services.browser.browser_service import BrowserService
from services.auth.login_service import LoginService

browser = BrowserService()
page = browser.launch()
try:
    LoginService(page).ensure_logged_in()
finally:
    browser.close()
