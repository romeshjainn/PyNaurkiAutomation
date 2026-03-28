"""
All job-filtering constants, pre-filter logic, and structural scoring.
No API calls — pure data-based decisions.

Score breakdown (max 100 + salary bonus):
  keywords   35  (AI, computed in job_scorer.py)
  recency    25  (scraped posted time)
  applicants 25  (scraped applicant count)
  experience 10  (scraped experience range)
  easy_apply  5  (easy apply button present)
  salary bonus   (additional on top)
"""

import re


# ── Constants ─────────────────────────────────────────────────────────────────

FILTERS = {
    "MAX_PAGES_PER_TYPE": 4,
    "DEAD_PAGES_LIMIT":   3,

    "MAX_APPLICANTS":  50,
    "MAX_EXP_YEARS":    3,
    "MIN_SALARY_LPA": 5.0,

    "HOT_SCORE":        88,
    "APPLY_MIN_SCORE":  80,
    "MIN_SCORE":        75,

    "WEIGHTS": {
        "keywords":   35,
        "recency":    25,
        "applicants": 25,
        "experience": 10,
        "easy_apply":  5,
    },

    "RECENCY_SCORE": {
        "under_3_hours":  25,
        "under_6_hours":  20,
        "under_12_hours": 15,
        "under_24_hours": 10,
        "yesterday":       5,
        "older":           0,
    },

    "APPLICANTS_SCORE": {
        "under_5":    25,
        "under_15":   20,
        "under_30":   15,
        "under_50":    8,
        "over_50":     0,
        "undisclosed": 10,
    },

    "EXP_SCORE": {
        "perfect":    10,
        "acceptable":  5,
        "too_senior":  0,
    },

    "SALARY_BONUS": {
        "above_8_lpa":   10,
        "above_6_lpa":    8,
        "above_5_5_lpa":  5,
        "not_disclosed":  5,
        "below_5_5_lpa":  0,
    },

    "TITLE_BLOCKLIST": [
        "java developer", "java engineer",
        "python developer", "python engineer",
        "php developer", "php engineer",
        ".net developer", ".net engineer",
        "devops", "devsecops",
        "qa engineer", "quality analyst", "test engineer", "automation test",
        "sap ", "salesforce", "servicenow",
        "data engineer", "data scientist", "machine learning",
        "ai engineer", "ml engineer",
        "embedded", "firmware",
        "android developer", "ios developer",
        "flutter developer", "flutter engineer",
        "angular developer", "vue developer",
        "wordpress", "magento", "shopify",
        "selenium", "appium", "cypress engineer",
        "blockchain", "solidity",
        "unity", "unreal",
        "cobol", "mainframe",
    ],
}

JOB_TARGETS = [
    {
        "type": "react",
        "mustHave": [
            "react", "reactjs", "react.js", "react js",
            "next.js", "nextjs", "next js",
            "frontend", "front end", "front-end",
            "ui developer", "ui engineer",
            "javascript", "typescript",
        ],
        "keywords": [
            "react", "react.js", "reactjs", "nextjs", "next.js",
            "redux", "zustand", "context api", "react query", "tanstack",
            "tailwind", "tailwindcss", "shadcn", "styled components", "material ui", "mui",
            "vite", "webpack", "typescript", "javascript", "es6",
            "frontend", "front end", "front-end", "html", "css", "sass", "scss",
            "ui developer", "ui engineer", "rest api", "graphql", "axios",
        ],
        "url": (
            "https://www.naukri.com/react-dot-js-react-js-developer-react-js-frontend-developer"
            "-react-developer-nextjs-typescript-javascript-jobs"
            "?k=react.js%2C%20react%20js%20developer%2C%20react%20js%20frontend%20developer"
            "%2C%20react%20developer%2C%20nextjs%2C%20typescript%2C%20javascript"
            "&nignbevent_src=jobsearchDeskGNB"
        ),
    },
    {
        "type": "mern",
        "mustHave": [
            "mern", "mern stack",
            "node.js", "nodejs", "node js",
            "backend", "back end", "back-end",
            "full stack", "fullstack", "full-stack",
            "express", "expressjs", "nestjs",
        ],
        "keywords": [
            "mern", "mern stack", "node.js", "nodejs", "express", "nestjs",
            "react", "reactjs", "mongodb", "mongoose", "postgresql", "postgres", "mysql",
            "full stack", "fullstack", "full-stack", "backend", "back end", "back-end",
            "rest api", "graphql", "api development", "jwt", "oauth", "redis",
            "javascript", "typescript",
        ],
        "url": (
            "https://www.naukri.com/mern-stack-mern-stack-developer-mern-full-stack-developer"
            "-frontend-development-frontend-software-developer-node-dot-js-backend-mern-stack"
            "-mern-express-nestjs-jobs"
            "?k=mern%20stack%2C%20mern%20stack%20developer%2C%20mern%20full%20stack%20developer"
            "%2C%20frontend%20development%2C%20frontend%20software%20developer%2C%20node.js"
            "%2C%20backend%2C%20mern%20stack%2C%20mern%2C%20express%2C%20nestjs"
            "&nignbevent_src=jobsearchDeskGNB"
        ),
    },
    {
        "type": "reactnative",
        "mustHave": [
            "react native", "reactnative", "react-native",
            "mobile developer", "mobile application",
            "android", "ios",
        ],
        "keywords": [
            "react native", "reactnative", "react-native",
            "expo", "expo go", "ios", "android", "mobile", "mobile app",
            "navigation", "react navigation",
            "redux", "zustand", "context api",
            "node.js", "nodejs", "express", "nestjs", "backend", "rest api",
            "javascript", "typescript",
        ],
        "url": (
            "https://www.naukri.com/react-native-react-native-developer-react-native-mobile"
            "-application-developer-node-dot-js-node-js-backend-developer-node-js-developer"
            "-backend-development-backend-react-native-jobs"
            "?k=react%20native%2C%20react%20native%20developer%2C%20react%20native%20mobile"
            "%20application%20developer%2C%20node.js%2C%20node%20js%20backend%20developer"
            "%2C%20node%20js%20developer%2C%20backend%20development%2C%20backend%2C%20react%20native"
            "&nignbevent_src=jobsearchDeskGNB"
        ),
    },
]


# ── Title filters ──────────────────────────────────────────────────────────────

def passes_title_filter(title: str) -> tuple[bool, str]:
    """Return (passes, reason). Rejects if title contains a blocklisted term."""
    t = title.lower()
    for term in FILTERS["TITLE_BLOCKLIST"]:
        if term in t:
            return False, f"blocklisted title term: '{term}'"
    return True, ""


def passes_must_have(title: str, description: str, must_have: list[str]) -> tuple[bool, str]:
    """Return (passes, reason). Job must contain at least one must-have keyword
    in the title or description."""
    combined = (title + " " + description).lower()
    for kw in must_have:
        if kw.lower() in combined:
            return True, ""
    return False, "no must-have keyword found"


# ── Pre-filter ─────────────────────────────────────────────────────────────────

def passes_pre_filter(job: dict) -> tuple[bool, str]:
    """Return (passes, reason). Reason is non-empty when rejected."""
    # Title blocklist
    ok, reason = passes_title_filter(job.get("title", ""))
    if not ok:
        return False, reason

    # Recency
    h = job.get("posted_hours")
    if h is not None and h > 48:
        return False, f"too old ({h:.0f}h)"

    # Applicants
    c = job.get("applicants_count")
    if c is not None and c > FILTERS["MAX_APPLICANTS"]:
        return False, f"too many applicants ({c})"

    # Experience
    exp_max = job.get("exp_max")
    if exp_max is not None and exp_max > FILTERS["MAX_EXP_YEARS"] + 1:
        return False, f"exp too senior (max {exp_max} yrs)"

    # Salary — only kill if disclosed AND clearly below minimum
    sal = job.get("salary_lpa_min")
    if sal is not None and sal > 0 and sal < FILTERS["MIN_SALARY_LPA"]:
        return False, f"salary too low ({sal} LPA)"

    return True, ""


# ── Structural scoring ─────────────────────────────────────────────────────────

def compute_structural_score(job: dict) -> int:
    score = 0

    # Recency
    h  = job.get("posted_hours")
    rs = FILTERS["RECENCY_SCORE"]
    if h is None:        score += rs["under_24_hours"]
    elif h <= 3:         score += rs["under_3_hours"]
    elif h <= 6:         score += rs["under_6_hours"]
    elif h <= 12:        score += rs["under_12_hours"]
    elif h <= 24:        score += rs["under_24_hours"]
    elif h <= 48:        score += rs["yesterday"]
    else:                score += rs["older"]

    # Applicants
    c  = job.get("applicants_count")
    ap = FILTERS["APPLICANTS_SCORE"]
    if c is None:   score += ap["undisclosed"]
    elif c < 5:     score += ap["under_5"]
    elif c < 15:    score += ap["under_15"]
    elif c < 30:    score += ap["under_30"]
    elif c < 50:    score += ap["under_50"]
    else:           score += ap["over_50"]

    # Experience
    exp_max = job.get("exp_max")
    es = FILTERS["EXP_SCORE"]
    if exp_max is None:    score += es["acceptable"]
    elif exp_max <= 2.5:   score += es["perfect"]
    elif exp_max <= 4:     score += es["acceptable"]
    else:                  score += es["too_senior"]

    # Easy apply
    if job.get("easy_apply"):
        score += FILTERS["WEIGHTS"]["easy_apply"]

    # Salary bonus
    sal = job.get("salary_lpa_min")
    sb  = FILTERS["SALARY_BONUS"]
    if sal is None or sal == 0: score += sb["not_disclosed"]
    elif sal >= 8:              score += sb["above_8_lpa"]
    elif sal >= 6:              score += sb["above_6_lpa"]
    elif sal >= 5.5:            score += sb["above_5_5_lpa"]
    else:                       score += sb["below_5_5_lpa"]

    return score


# ── Parsing helpers ────────────────────────────────────────────────────────────

def parse_experience(raw: str) -> tuple[float | None, float | None]:
    if not raw:
        return None, None
    nums = re.findall(r"\d+(?:\.\d+)?", raw)
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    if len(nums) == 1:
        v = float(nums[0])
        return v, v
    return None, None


def parse_salary_lpa(raw: str) -> float | None:
    if not raw or not raw.strip():
        return None
    if any(x in raw.lower() for x in ["not disclosed", "undisclosed", "n/a", "--"]):
        return None
    nums = re.findall(r"\d+(?:\.\d+)?", raw)
    return float(nums[0]) if nums else None


def parse_posted_hours(raw: str) -> float | None:
    if not raw:
        return None
    r = raw.lower().strip()
    if any(x in r for x in ["just now", "few minutes", "1 minute", "minutes ago"]):
        return 0.1
    m = re.search(r"(\d+)\s*(minute|hour|day|week|month)", r)
    if not m:
        return None
    val, unit = int(m.group(1)), m.group(2)
    if "minute" in unit: return val / 60
    if "hour"   in unit: return float(val)
    if "day"    in unit: return float(val * 24)
    if "week"   in unit: return float(val * 24 * 7)
    if "month"  in unit: return float(val * 24 * 30)
    return None


def parse_applicants(raw: str) -> int | None:
    if not raw:
        return None
    if "+" in raw:
        nums = re.findall(r"\d+", raw)
        return int(nums[0]) + 1 if nums else None
    nums = re.findall(r"\d+", raw)
    return int(nums[0]) if nums else None
