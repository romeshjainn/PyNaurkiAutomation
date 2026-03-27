# PyNaurkiAutomation

Python-based automation bot for managing a Naukri.com account — keeping the profile active and applying to jobs daily.

## Project Goals

1. **Login management** — detect existing session or authenticate
2. **Profile updates** — update headline, summary, resume periodically
3. **Job matching** — use NVIDIA LLM API to match jobs against user profile
4. **Job applications** — apply to 2–4 relevant jobs daily
5. **Human simulation** — random delays, typing rhythm, mouse movement to avoid bot detection
6. **Scheduling** — run at randomized/scheduled times

## Architecture

Service-based. Each service is fully independent — the `orchestrator` is the only component that connects services. Changing one service never requires touching another.

## Folder Structure

```
PyNaurkiAutomation/
├── main.py                            # Entry point
├── requirements.txt                   # playwright, python-dotenv
├── .env                               # Credentials (never commit)
├── .env.example                       # Template for .env
├── config/
│   ├── settings.py                    # Env loading, URLs, constants
│   └── profile.json                   # User profile for LLM matching (planned)
├── services/
│   ├── locators/
│   │   └── naukri_locators.py         # ALL selectors — single source of truth
│   ├── browser/
│   │   └── browser_service.py         # Launch/close Playwright browser
│   ├── auth/
│   │   └── login_service.py           # Session check, login, OTP handling
│   ├── profile/
│   │   └── profile_service.py         # Update headline, summary, resume (planned)
│   ├── jobs/
│   │   └── job_service.py             # Search, scrape, apply (planned)
│   ├── matcher/
│   │   └── llm_service.py             # NVIDIA LLM job-profile matching (planned)
│   ├── human/
│   │   └── delay_service.py           # Human-like delays + interaction (planned)
│   └── scheduler/
│       └── scheduler_service.py       # Randomized scheduling (planned)
├── core/
│   ├── utils.py                       # try_selectors() — fallback selector helper
│   └── orchestrator.py                # Composes services, defines daily run flow
└── logs/
    └── app.log
```

## Services Overview

| Service | Responsibility | Status |
|---------|---------------|--------|
| `browser_service` | Launch/close Playwright browser | **Done** |
| `login_service` | Session check, login, OTP handling | **Done** |
| `naukri_locators` | All UI selectors (CSS/Playwright) | **Active** — login + OTP selectors added |
| `profile_service` | Update headline, summary, resume | Planned |
| `job_service` | Search jobs, scrape details, apply | Planned |
| `llm_service` | NVIDIA LLM job-profile matching | Planned |
| `delay_service` | Human-like delays and interactions | Planned |
| `scheduler_service` | Randomized scheduling | Planned |
| `orchestrator` | Connects all services, runs daily flow | **Active** — login step wired |

## Key Design Decisions

- `locators/naukri_locators.py` is the **only** place selectors live — UI changes = one file edit
- `core/utils.py::try_selectors()` — tries each selector in order, returns first visible match
- `BrowserService` owns the Playwright lifecycle (launch + close)
- `LoginService._handle_otp_if_present()` waits up to 120s for manual OTP entry
- `orchestrator` is the only place services are composed — services have zero knowledge of each other
- `profile.json` (planned) — profile data lives outside code for easy updates without touching services

## Running

```bash
# 1. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 2. Set credentials
cp .env.example .env
# Edit .env with your Naukri email and password

# 3. Run
python main.py
```

## Build Log

| Step | Description | Status |
|------|-------------|--------|
| 0 | Project planning & folder structure design | Done |
| 1 | Folder setup, Playwright browser, login service, locators | **Done** |
