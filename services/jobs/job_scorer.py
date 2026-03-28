"""
Scores each job using two signals combined into a final score (0-100+).

  LLM score (35%)  — Groq llama-3.3-70b-versatile judges keyword/skill fit
                     against the candidate's profile
  Structural score (65%) — recency, applicants, experience, easy_apply, salary

Combined = (llm_score × 0.35) + (structural_score × 0.65)
"""

import logging
import re

import httpx

from config.profile_content import (
    ACHIEVEMENTS,
    EXPERIENCE,
    NAME,
    PROJECTS,
    SKILLS,
    TOTAL_EXPERIENCE_YEARS,
)
from config.settings import GROQ_API_KEY
from services.jobs.job_filters import compute_structural_score

logger = logging.getLogger(__name__)

GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# Build profile string once at import time — used in every LLM prompt
_PROFILE = f"""
Name: {NAME}
Total Experience: {TOTAL_EXPERIENCE_YEARS}

Experience:
{EXPERIENCE}

Skills:
{SKILLS}

Projects:
{PROJECTS}

Achievements:
{ACHIEVEMENTS}
""".strip()


class JobScorer:
    # ── Public ────────────────────────────────────────────────────────────────

    def score(self, job: dict) -> dict:
        """Compute and attach scores to the job dict. Returns the same dict."""
        structural = compute_structural_score(job)
        llm        = self._llm_score(job)
        combined   = round((llm * 0.35) + (structural * 0.65), 1)

        job["llm_score"]        = llm
        job["structural_score"] = structural
        job["combined_score"]   = combined

        logger.info(
            "Scored '%s': LLM=%d  structural=%d  combined=%.1f",
            job.get("title"), llm, structural, combined,
        )
        return job

    def score_batch(self, jobs: list[dict]) -> list[dict]:
        for job in jobs:
            self.score(job)
        return sorted(jobs, key=lambda j: j.get("combined_score", 0), reverse=True)

    # ── Private ───────────────────────────────────────────────────────────────

    def _llm_score(self, job: dict) -> float:
        prompt = self._build_prompt(job)
        try:
            response = httpx.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":       GROQ_MODEL,
                    "messages":    [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens":  10,
                },
                timeout=30,
            )
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"].strip()
            m = re.search(r"\d+", text)
            return float(m.group()) if m else 50.0
        except Exception as e:
            logger.warning("LLM scoring failed for '%s': %s — defaulting to 50", job.get("title"), e)
            return 50.0

    @staticmethod
    def _build_prompt(job: dict) -> str:
        skills_str = ", ".join(job.get("skills", [])) if job.get("skills") else "not listed"
        return f"""You are evaluating a job listing for a software engineer candidate.
Score the job's fit with the candidate's profile from 0 to 100 based strictly on:
- Skill and tech stack match
- Role and seniority alignment
- Keyword overlap between job requirements and candidate's experience

CANDIDATE PROFILE:
{_PROFILE}

JOB TITLE: {job.get('title', '')}
COMPANY: {job.get('company', '')}
REQUIRED SKILLS: {skills_str}
JOB DESCRIPTION:
{job.get('description', '')[:2000]}

Return ONLY a single integer between 0 and 100. No explanation, no text."""
