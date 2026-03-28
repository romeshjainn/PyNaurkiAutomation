import os
from dotenv import load_dotenv

load_dotenv()

# Credentials
NAUKRI_EMAIL: str = os.getenv("NAUKRI_EMAIL", "")
NAUKRI_PASSWORD: str = os.getenv("NAUKRI_PASSWORD", "")
GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
REPORT_EMAIL: str = os.getenv("REPORT_EMAIL", os.getenv("NAUKRI_EMAIL", ""))
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# URLs
NAUKRI_BASE_URL = "https://www.naukri.com"
NAUKRI_PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
# Direct login URL — redirects to profile after login, or straight to profile if already logged in
NAUKRI_LOGIN_URL = "https://www.naukri.com/nlogin/login"

# Browser
BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"

# Session
SESSION_FILE = "session.json"
