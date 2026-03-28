# PyNaurkiAutomation

Python-based Playwright bot that keeps a Naukri.com profile active and applies to jobs daily — fully automated, human-simulated, LLM-scored.

---

## Full Bot Walkthrough — Every Step in Order

This is exactly what the bot does from the moment you run it to the moment the day ends.

---

### STEP 1 — Scheduler Wakes Up
**File:** `scheduler_service.py`

The bot runs as a continuous loop. At startup it picks two random run times for the day:
- **Morning session:** somewhere between 7:00 AM and 11:00 AM
- **Afternoon session:** somewhere between 2:00 PM and 5:00 PM

Both times are picked using a **Gaussian distribution centred at the midpoint** of each window (σ = 25% of window width) so runs don't cluster at the edges and look like a real person's schedule. The bot then sleeps until morning time arrives.

---

### STEP 2 — Browser Launches
**File:** `browser_service.py`

Playwright launches a **Chromium browser** (headful by default — `BROWSER_HEADLESS=false`). If a previous session cookie file (`session.json`) exists from a prior run, it is loaded into the browser context so Naukri sees a returning user, not a fresh one.

---

### STEP 3 — Login Check
**File:** `login_service.py`

The bot navigates directly to `https://www.naukri.com/mnjuser/profile`.
- **If it lands on the profile page** → session is still valid, login skipped entirely.
- **If Naukri redirects to the login page** → session expired or missing, proceed to login.

#### Login flow (when needed):
1. Navigates to `https://www.naukri.com/nlogin/login`
2. Fills the email field with `NAUKRI_EMAIL` from `.env` — 400ms pause after
3. Fills the password field with `NAUKRI_PASSWORD` from `.env` — 400ms pause after
4. Clicks the Login/Submit button

#### OTP handling (automatic — no manual action needed):
If Naukri shows the OTP verification screen after login:
1. Bot detects the 6-digit split input fields (`input#Input_1` through `input#Input_6`)
2. Connects to Gmail via **IMAP** (`imap.gmail.com:993`) using the same Gmail + App Password
3. Searches the inbox for email from `info@naukri.com` with subject `"Your OTP for logging in Naukri account"`
4. Polls every **4 seconds** for up to **60 seconds** until the email arrives
5. Extracts the 6-digit OTP from the email body using regex
6. Types each digit into its own input field with **120ms delay** between digits
7. Clicks the Verify/Submit button

After successful login the session state is saved to `session.json` for reuse next time.

---

### STEP 4 — Profile Update (Morning Only)
**File:** `profile_service.py`, `content_generator.py`

#### 4a. Read current headline and summary
- Opens the headline edit form, reads the textarea value, hits Escape to cancel (no change made)
- Opens the summary edit form, reads the textarea value, hits Escape to cancel
- These live values are passed to the AI so it generates something *different* — not a rewrite of the same text

#### 4b. Generate and upload AI resume
- Calls `resume_code/generate_resume.py` which uses a LaTeX template + Tectonic to compile a fresh PDF
- If generation fails for any reason, falls back to the static `resume.pdf` in the project root
- Finds the resume upload input (`input#attachCV`) on the profile page
- Uploads the PDF via Playwright's `set_input_files()`
- If Naukri shows a "Replace resume?" confirmation dialog, confirms it
- Waits 4 seconds for upload to complete
- **Saves a copy to `data/last_resume.pdf`** before cleaning up (used as email attachment later)
- Deletes the `resume_code/resume/` output folder — regenerated fresh every day

#### 4c. Generate new headline and summary via Groq AI
Sends a request to **Groq API** (`llama-3.3-70b-versatile`, temperature=0.4) with:
- The current live headline + summary (so AI doesn't repeat them)
- Full candidate profile from `config/profile_content.py`: name, total experience, work history, technical skills, key projects, achievements/certifications

AI returns a JSON object with a fresh `headline` (max 250 chars) and `summary` (max 1000 chars).
Hard limits are enforced in code after the response — trimmed at last `|` or `.` if exceeded.

#### 4d. Save headline to Naukri
1. Clicks the headline edit icon
2. Waits for `form[name='resumeHeadlineForm']` to appear
3. Fills `textarea#resumeHeadlineTxt` with the new headline
4. Clicks the save button (`button.btn-dark-ot`)
5. Waits for the form to disappear (saved)
6. Dismisses the post-save confirmation modal if it appears

#### 4e. Save summary to Naukri
Same flow as headline but with `form[name='profileSummaryForm']` and `textarea#profileSummaryTxt`. The bot scrolls down in 400px increments until the summary widget is visible before clicking edit.

---

### STEP 5 — Decoy Browsing (Human Simulation)
**File:** `job_session.py` → `_decoy_browse()`

Before applying to any jobs the bot **pretends to be a person browsing**:
1. Navigates to one of the job search URLs
2. Waits 2–4 seconds
3. Scrolls the page in 3–7 irregular steps (250–600px each, 20% chance of scrolling up), pausing 1.5–3.5s between steps
4. Picks 2–3 random job cards from the listing
5. Clicks into each one, dwells for **8–20 seconds** while scrolling the page
6. Clicks browser Back, waits 1.5–3 seconds
7. Repeats for each decoy job

This runs **only in the morning session** and **only in production mode** (skipped in TEST_MODE).

---

### STEP 6 — Scrape Job Listings
**File:** `job_scraper.py`

The bot scrapes **3 job search targets** in sequence:
1. **React / Next.js / TypeScript** jobs
2. **MERN Stack / Node.js / Full Stack** jobs
3. **React Native / Mobile** jobs

For each target:
1. Navigates to the pre-built Naukri search URL
2. Waits 2.5–4 seconds for page to load (800–1500ms in TEST_MODE)
3. **Sorts by Date** — opens the sort dropdown (`button#filter-sort`), waits 500ms, clicks the Date option (`a[data-id='filter-sort-f']`), waits for page to reload. This is done once on page 1. **Next-button navigation preserves the sort** — URL-based navigation would reset it.
4. Reads all job cards (`div.srp-jobtuple-wrapper`) on the page
5. For each card extracts:
   - `job_id` — from `data-job-id` attribute directly on the wrapper (stable, always present)
   - Title and URL — from `a.title`
   - Company — from `a.comp-name`
   - Salary — from `.sal-wrap`
   - Experience — from `span.expwdth` (e.g. "1-3 Yrs" parsed to min/max floats)
   - Posted time — from `span.job-post-day` (e.g. "4 days ago" parsed to hours float)
   - Applicants — from `span[title*='applicant']`
6. Paginates by clicking the **Next button** (`#lastCompMark a:has-text('Next')`). Waits 8–15 seconds between pages (1s in TEST_MODE). Falls back to URL-based pagination + re-sort if Next button not found.
7. Stops when 15 passing jobs are collected or 4 pages reached

Duplicate job IDs across the 3 targets are dropped. Final list is all unique candidates.

---

### STEP 7 — Pre-Filter (Static, No AI)
**File:** `job_filters.py` → `passes_pre_filter()`

Each scraped job is checked against hard rules — any failure immediately drops the job:

| Check | Rule |
|-------|------|
| Title blocklist | Drop if title contains: Java, Python, PHP, .NET, DevOps, QA, SAP, Salesforce, Data Scientist, ML, Flutter, Angular, Vue, WordPress, Blockchain, Unity, COBOL, etc. |
| Recency | Drop if posted more than **48 hours** ago |
| Applicants | Drop if more than **50 applicants** have already applied |
| Experience | Drop if the job requires more than **4 years** max experience |
| Salary | Drop if salary is disclosed AND below **5 LPA** |

**Afternoon session adds one extra rule:** drop if posted more than **6 hours** ago (fresh jobs only).

---

### STEP 8 — Visit Each Job Detail Page
**File:** `job_detail.py`

For every job that passed pre-filter, the bot visits the job's full page:
1. Navigates to the job URL, waits 1.5–3 seconds
2. Checks for `button#apply-button` (or `button.apply-button`) — this is the **Easy Apply gate**
   - If the button is **not present** → `easy_apply = False` → job is dropped here, no AI call wasted
   - If the button is **present** → `easy_apply = True` → proceed
3. Grabs the full job description text
4. Grabs the required skills list
5. Dwells on the page for **5–15 seconds** (simulates reading the JD)

---

### STEP 9 — Must-Have Keyword Check
**File:** `job_filters.py` → `passes_must_have()`

Each easy-apply job's title + full description is checked for at least one must-have keyword from its target group:
- **React target:** react, reactjs, next.js, nextjs, frontend, ui developer, javascript, typescript, etc.
- **MERN target:** mern, node.js, nodejs, express, nestjs, fullstack, backend, etc.
- **React Native target:** react native, expo, mobile developer, android, ios, etc.

Jobs with none of these in the title or description are dropped — they likely appeared in search results by accident.

---

### STEP 10 — LLM Scoring
**File:** `job_scorer.py`

Each surviving job gets **two scores** combined:

#### Structural score (65% weight) — pure data, no API call:
| Factor | Max Points |
|--------|-----------|
| Recency: posted ≤3h ago | 25 |
| Recency: posted ≤6h ago | 20 |
| Recency: posted ≤12h ago | 15 |
| Recency: posted ≤24h ago | 10 |
| Recency: posted ≤48h ago | 5 |
| Applicants: <5 | 25 |
| Applicants: <15 | 20 |
| Applicants: <30 | 15 |
| Applicants: <50 | 8 |
| Experience: perfect fit (≤2.5 yrs max) | 10 |
| Experience: acceptable (≤4 yrs max) | 5 |
| Easy apply button present | 5 |
| Salary bonus: ≥8 LPA | 10 |
| Salary bonus: ≥6 LPA | 8 |
| Salary bonus: ≥5.5 LPA | 5 |
| Salary not disclosed | 5 |

#### LLM score (35% weight) — Groq API call:
Sends job title, company, required skills, and job description (first 2000 chars) + full candidate profile to `llama-3.3-70b-versatile` (temperature=0.1, max_tokens=10).
Model returns a single integer 0–100 based on skill match, role alignment, and keyword overlap.
If the API call fails, defaults to 50.

**Combined = (LLM × 0.35) + (structural × 0.65)**

Jobs are sorted by combined score descending. All scores are saved to `data/jobs.db`.

---

### STEP 11 — Apply Queue
**File:** `job_session.py`

Only jobs with `combined_score >= 80` enter the apply queue.
The bot picks a random target count:
- Morning: **4–6 applications** (2 in TEST_MODE)
- Afternoon: **3–5 applications** (2 in TEST_MODE)

---

### STEP 12 — Apply to Each Job
**File:** `job_applicant.py`, `job_chatbot.py`

For each job in the queue:

#### 12a. Navigate to job page
Goes to the job URL, waits 2 seconds, checks for CAPTCHA and already-applied indicators first.

#### 12b. Click Apply button
Wraps the click in a popup listener:
- **New tab opens** → external company website → close the tab, skip this job, move on
- **Page redirects off naukri.com** → go back, skip this job
- **Stayed on Naukri** → proceed

#### 12c. Detect which apply flow triggered

**Flow A — Chatbot drawer** (`div.chatbot_DrawerContentWrapper` appears within 5 seconds):
The bot drives a full Q&A conversation:
1. Waits for a new bot message to appear (polls every 400ms, timeout 10s)
2. Reads the latest question text
3. Checks if it contains "Thank you" → application complete, return True
4. Checks `CHIP_ANSWERS` dict for clickable options (Yes/No chips):
   - "relocate" / "relocation" → clicks **Yes**
   - "work from office" / "hybrid" → clicks **Yes**
   - "immediate joiner" → clicks **No**
   - "fresher" → clicks **No**
   - "currently employed" → clicks **Yes**
5. If no chip match, checks `TEXT_ANSWERS` dict and types into the contenteditable input (`div.textArea[contenteditable='true']`):
   - "years of experience" / "total experience" / "how many years" → types **"2"**
   - "portfolio" / "website" / "profile link" → types **"https://romeshjain.netlify.app/"**
   - "github" → types **"https://github.com/RomeshJain7"**
   - "notice period" → types **"30"**
   - "current ctc" / "current salary" → types **"5"**
   - "expected ctc" / "expected salary" → types **"8"**
   - "current location" → types **"Indore"**
   - "preferred location" → types **"Remote"**
   - "gender" → types **"Male"**
   - "highest qualification" / "degree" → types **"B.Tech"**
   - Unknown question → types default **"2"**
6. Waits **0.8 seconds** after typing, clicks Send (`div.sendMsg`), waits **3 seconds** for next bot message
7. Repeats for up to **20 questions** (safety cap)

**Flow B — Direct apply** (no drawer):
Naukri applied immediately without asking anything. Bot checks for success indicators (disabled Apply button, success banner). If found → mark applied.

**Flow C — Failed** (neither chatbot nor success signal):
Marks as retriable, tries up to **2 times** total with **5 second** gap between retries.

#### 12d. Inter-application delay
After each successful application (except the last one), waits:
**3–8 minutes** + Gaussian jitter (±30 seconds), minimum 1 minute.
In TEST_MODE this delay is completely skipped.

---

### STEP 13 — Save Results to Database
**File:** `job_store.py` — SQLite at `data/jobs.db`

Every job that passes pre-filter is inserted into the DB. Status updates through the pipeline:
- `new` → `scored` → `applied` / `skipped` / `error`

Applied jobs are **never deleted**. On the next run, `applied_today_ids()` checks the DB first — any job already in the DB with `status='applied'` is skipped before scraping even begins.

---

### STEP 14 — Afternoon Session
Same as steps 6–13 but:
- No profile update
- No decoy browsing
- Extra filter: only jobs posted ≤ 6 hours ago
- Target: 3–5 applications

---

### STEP 15 — End-of-Day Email Report
**File:** `email_service.py`

After the afternoon session completes, sends an HTML email via **Gmail SMTP** (`smtp.gmail.com:587`, STARTTLS) using the Gmail App Password:

**Email contains:**
- **Headline:** previous text → new AI-generated text
- **Summary:** previous text → new AI-generated text (full before/after)
- **Resume:** `data/last_resume.pdf` attached to the email
- **Jobs applied table:** job title (linked), company, combined score — one row per application
- **Errors section:** any crashes or warnings from the day (only shown if errors occurred)

If `REPORT_EMAIL` is set in `.env`, report goes there. Otherwise goes to `NAUKRI_EMAIL` (send to self).

---

### STEP 16 — Cleanup
**File:** `job_store.py` → `purge_non_applied()`

After the report is sent:
- All DB rows with status `new`, `scored`, `skipped`, or `error` are **deleted**
- Rows with status `applied` are **kept forever**

This keeps the database lean while maintaining a permanent history of every job ever applied to — so the bot never applies to the same job twice, even months later.

---

### STEP 17 — Sleep Until Tomorrow
Scheduler sleeps 60 seconds then loops back to Step 1, picking new random times for the next day.

---

## What It Does (Daily Flow)

### Morning Session (7 AM – 11 AM, Gaussian-randomized)
1. **Login** — checks saved session cookie; if expired, logs in with email/password and waits up to 120s for manual OTP
2. **Profile update**
   - Scrapes current headline + summary (opens edit form, reads textarea, cancels)
   - Generates a fresh AI resume PDF via Tectonic + Groq LLM
   - Uploads resume to Naukri (replaces existing)
   - Generates new headline + summary via Groq LLM (`llama-3.3-70b-versatile`)
   - Saves updated headline + summary on Naukri
3. **Decoy browsing** — visits 2–3 random job pages without applying (8–20s dwell each)
4. **Scrape** — hits all 3 job search targets (React, MERN, React Native), sorts by Date, paginates via Next button
5. **Pre-filter** — drops jobs by title blocklist, experience range, salary floor, applicant ceiling, recency
6. **Detail fetch** — visits each passing job's page, checks for `button#apply-button` (easy apply gate), grabs description + skills
7. **Must-have check** — drops jobs missing required keywords in title/description
8. **LLM scoring** — Groq scores each job 1–10; combined = (LLM × 0.35) + (structural × 0.65)
9. **Apply** (target: 4–6 jobs, capped at combined_score ≥ threshold)
   - Detects external-redirect apply (popup opens → close, skip)
   - Detects chatbot drawer → drives Q&A (text + chip answers)
   - Detects direct apply (no drawer, Naukri applies immediately)
   - 3–8 min randomized delay between each application

### Afternoon Session (2 PM – 5 PM, Gaussian-randomized)
- Same scrape → filter → score → apply pipeline
- Extra filter: only jobs posted **≤ 6 hours ago**
- Target: 3–5 applications
- No profile update (morning only)

### End of Day (after afternoon session)
- Sends HTML report email to Gmail with:
  - Headline before → after
  - Summary before → after
  - Resume PDF attached
  - Table of all jobs applied (title, company, score, link)
  - Any errors/crashes from the day
- **Purges** all non-applied rows from DB — applied rows kept forever for dedup

---

## Key Delays & Timing

| Where | Delay | Why |
|-------|-------|-----|
| Session start | Gaussian within window (σ = 25% of window) | Looks like a human opening a browser |
| Page load wait | 800ms–4s (TEST_MODE: 800–1500ms) | Let DOM settle |
| Sort-by-date | 500ms after opening dropdown | React state update |
| Pagination | 8–15s between pages (TEST_MODE: 1s) | Simulate reading |
| Detail page dwell | 5–15s per job | Simulate reading the JD |
| Answer delay (chatbot) | 0.8s after typing/clicking chip | Simulate thinking |
| Wait for next Q | 3s after clicking Send | Bot response time |
| Inter-application | 3–8 min + Gaussian jitter ±30s (min 1 min) | Core anti-bot gap |
| Decoy dwell | 8–20s per decoy job | Simulate reading |
| Scroll pause | 1.5–3.5s between scroll steps | Human scroll rhythm |

---

## Architecture

Service-based. No service imports another — `scheduler_service` is the only composer.

```
PyNaurkiAutomation/
├── main.py                          # Legacy entry (profile only) — use scheduler instead
├── config/
│   ├── settings.py                  # Env vars: credentials, URLs, REPORT_EMAIL
│   └── profile_content.py           # Static profile data fed to LLM scorer
├── services/
│   ├── locators/
│   │   └── naukri_locators.py       # ONLY place selectors live — UI change = edit here
│   ├── browser/
│   │   └── browser_service.py       # Playwright launch/close, persistent session.json
│   ├── auth/
│   │   └── login_service.py         # Session check → login → OTP (120s manual window)
│   ├── profile/
│   │   ├── profile_service.py       # Headline/summary/resume update; returns before/after dict
│   │   └── content_generator.py     # Groq LLM generates headline + summary
│   ├── jobs/
│   │   ├── job_filters.py           # FILTERS config, JOB_TARGETS, all filter/parse functions
│   │   ├── job_store.py             # SQLite (data/jobs.db) — dedup, scores, applied history
│   │   ├── job_scraper.py           # Scrape listing pages, sort by date, paginate
│   │   ├── job_detail.py            # Visit each job, detect easy-apply, get description
│   │   ├── job_scorer.py            # Groq LLM score + structural score → combined
│   │   ├── job_applicant.py         # Click apply, detect flow type, handle result
│   │   ├── job_chatbot.py           # Drive chatbot Q&A drawer (TEXT_ANSWERS + CHIP_ANSWERS)
│   │   └── job_session.py           # Pipeline orchestrator — TEST_MODE flag here
│   ├── notifier/
│   │   └── email_service.py         # Gmail SMTP — daily report + error alerts
│   └── scheduler/
│       └── scheduler_service.py     # Gaussian scheduling loop — entry point for production
├── core/
│   ├── utils.py                     # try_selectors() — tries selector list, returns first match
│   └── orchestrator.py              # (Legacy) — wired for profile only
├── data/
│   ├── jobs.db                      # SQLite — never delete, holds applied job history
│   └── last_resume.pdf              # Copy of last uploaded resume for email attachment
└── logs/
    └── app.log
```

---

## Services Overview

| Service | Responsibility | Status |
|---------|---------------|--------|
| `browser_service` | Playwright launch/close, session persistence | Done |
| `login_service` | Session check, email/password login, OTP | Done |
| `naukri_locators` | All CSS/Playwright selectors | Done |
| `profile_service` | Headline, summary, resume update | Done |
| `content_generator` | Groq LLM headline + summary generation | Done |
| `job_filters` | Filter constants, targets, parse helpers | Done |
| `job_store` | SQLite dedup + apply tracking + purge | Done |
| `job_scraper` | Listing scrape, date sort, pagination | Done |
| `job_detail` | Detail page fetch, easy-apply detection | Done |
| `job_scorer` | Groq LLM + structural scoring | Done |
| `job_applicant` | Apply button, popup/redirect guard, chatbot | Done |
| `job_chatbot` | Chatbot drawer Q&A driver | Done |
| `job_session` | Full session pipeline (morning/afternoon) | Done |
| `email_service` | Daily report + error alert emails | Done |
| `scheduler_service` | Gaussian-randomized daily scheduler | Done |

---

## Apply Flow — 3 Cases Handled

```
Click apply
    │
    ├─► New tab opened?  ──YES──► External company site → close tab, skip job
    │
    ├─► Redirected off naukri.com?  ──YES──► go_back(), skip job
    │
    └─► Stayed on Naukri
            │
            ├─► Chatbot drawer appeared (div.chatbot_DrawerContentWrapper)?
            │       └─► Drive Q&A until "Thank you" → mark applied
            │
            └─► No drawer → check success indicators
                    └─► Button disabled / success banner → mark applied
```

---

## Job Pipeline — Step by Step

```
scrape_all_targets()
    └─► per target: goto URL → sort by Date → paginate (Next btn)
            └─► _parse_card() — reads data-job-id from wrapper attribute

passes_pre_filter()  ← title blocklist, exp range, salary floor, applicants ceiling, recency

[afternoon only] posted_hours <= 6

enrich_batch()  ← visit detail page, _has_easy_apply(), description, skills
    └─► easy_apply = False → skip (no LLM call wasted)

passes_must_have()  ← mustHave keywords in title OR description

score_batch()  ← Groq LLM 1-10 + structural score
    └─► combined = (llm × 0.35) + (structural × 0.65)

apply_queue  ← combined_score >= APPLY_MIN_SCORE

applicant.apply()  ← per job, with inter-application delay
```

---

## Key Design Decisions

- `naukri_locators.py` is the **only** place selectors live — UI changes = one file edit
- `try_selectors()` tries a list of fallback selectors, returns first visible match
- `data-job-id` attribute on `div.srp-jobtuple-wrapper` is the stable job ID source
- Sort by Date done once on page 1; Next-button navigation preserves it (URL nav resets it)
- Easy-apply gating happens on the detail page — no LLM call on non-easy-apply jobs
- `data/jobs.db` applied rows are **never deleted** — permanent dedup history
- `TEST_MODE = True` in `job_session.py` — strips all delays, caps at 2 jobs. Flip to False for production
- Gmail SMTP uses App Password (not account password) — set `GMAIL_APP_PASSWORD` in `.env`
- `REPORT_EMAIL` defaults to `NAUKRI_EMAIL` if not set — send report to self

---

## Running

```bash
# Install
pip install -r requirements.txt
playwright install chromium

# Configure
cp .env.example .env
# Fill in: NAUKRI_EMAIL, NAUKRI_PASSWORD, GMAIL_APP_PASSWORD, GROQ_API_KEY

# Test run (TEST_MODE=True in job_session.py — 2 jobs, no delays)
python -m services.scheduler.scheduler_service

# Production (set TEST_MODE=False first)
python -m services.scheduler.scheduler_service
```

---

## Chatbot Pre-configured Answers

Edit `TEXT_ANSWERS` and `CHIP_ANSWERS` at the top of `job_chatbot.py` when new question types appear.
Current coverage: experience, portfolio/GitHub, notice period, CTC, location, gender, qualification, relocation, WFO/hybrid, employment status.

---

## .env Keys

| Key | Purpose |
|-----|---------|
| `NAUKRI_EMAIL` | Naukri login + Gmail sender address |
| `NAUKRI_PASSWORD` | Naukri password |
| `GMAIL_APP_PASSWORD` | 16-char Google App Password for SMTP |
| `REPORT_EMAIL` | Where to send daily report (defaults to NAUKRI_EMAIL) |
| `GROQ_API_KEY` | Groq API for LLM scoring + content generation |
| `BROWSER_HEADLESS` | `true`/`false` — headless browser mode |
