"""
SQLite-backed job store.
Tracks every job seen, scored, and applied to across all sessions.
Prevents double-applying the same job on the same or future days.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("data/jobs.db")


class JobStore:
    def __init__(self):
        DB_PATH.parent.mkdir(exist_ok=True)
        self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_table()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _create_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id           TEXT PRIMARY KEY,
                title            TEXT,
                company          TEXT,
                url              TEXT,
                salary           TEXT,
                applicants       TEXT,
                posted_time      TEXT,
                easy_apply       INTEGER DEFAULT 0,
                llm_score        REAL,
                structural_score REAL,
                combined_score   REAL,
                status           TEXT DEFAULT 'new',
                status_reason    TEXT,
                applied_at       TEXT,
                created_at       TEXT DEFAULT (datetime('now'))
            )
        """)
        self._conn.commit()

    # ── Reads ──────────────────────────────────────────────────────────────────

    def exists(self, job_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        return row is not None

    def applied_today_ids(self) -> set[str]:
        """Return job_ids that were applied to today (any session)."""
        today = datetime.now().date().isoformat()
        rows = self._conn.execute(
            "SELECT job_id FROM jobs WHERE status = 'applied' AND applied_at LIKE ?",
            (f"{today}%",),
        ).fetchall()
        return {r["job_id"] for r in rows}

    def total_applied_today(self) -> int:
        return len(self.applied_today_ids())

    def applied_today_details(self) -> list[dict]:
        """Return full details for jobs applied today — used in daily report."""
        today = datetime.now().date().isoformat()
        rows = self._conn.execute(
            """SELECT title, company, url, combined_score, applied_at
               FROM jobs WHERE status='applied' AND applied_at LIKE ?
               ORDER BY applied_at""",
            (f"{today}%",),
        ).fetchall()
        return [dict(r) for r in rows]

    def purge_non_applied(self):
        """Delete all rows that were never applied to.

        Applied rows are kept forever — they are the permanent dedup history
        that prevents re-applying to the same job in future sessions.
        """
        deleted = self._conn.execute(
            "DELETE FROM jobs WHERE status != 'applied'"
        ).rowcount
        self._conn.commit()
        logger.info("Purged %d non-applied rows — applied history preserved", deleted)

    # ── Writes ─────────────────────────────────────────────────────────────────

    def insert_new(self, job: dict):
        """Insert a freshly scraped job. Skips silently if job_id already exists."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO jobs
                (job_id, title, company, url, salary, applicants, posted_time, easy_apply, status)
            VALUES
                (:job_id, :title, :company, :url, :salary, :applicants, :posted_time, :easy_apply, 'new')
            """,
            {
                "job_id":    job["job_id"],
                "title":     job.get("title", ""),
                "company":   job.get("company", ""),
                "url":       job.get("url", ""),
                "salary":    job.get("salary_raw", ""),
                "applicants": job.get("applicants_raw", ""),
                "posted_time": job.get("posted_raw", ""),
                "easy_apply": int(job.get("easy_apply", False)),
            },
        )
        self._conn.commit()

    def update_scores(
        self,
        job_id: str,
        llm_score: float,
        structural_score: float,
        combined_score: float,
    ):
        self._conn.execute(
            """
            UPDATE jobs
            SET llm_score=?, structural_score=?, combined_score=?, status='scored'
            WHERE job_id=?
            """,
            (llm_score, structural_score, combined_score, job_id),
        )
        self._conn.commit()

    def mark_applied(self, job_id: str):
        self._conn.execute(
            "UPDATE jobs SET status='applied', applied_at=? WHERE job_id=?",
            (datetime.now().isoformat(), job_id),
        )
        self._conn.commit()

    def mark_skipped(self, job_id: str, reason: str):
        self._conn.execute(
            "UPDATE jobs SET status='skipped', status_reason=? WHERE job_id=?",
            (reason, job_id),
        )
        self._conn.commit()

    def mark_error(self, job_id: str, reason: str):
        self._conn.execute(
            "UPDATE jobs SET status='error', status_reason=? WHERE job_id=?",
            (reason, job_id),
        )
        self._conn.commit()

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def close(self):
        self._conn.close()
