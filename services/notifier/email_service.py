"""
Gmail SMTP email service.

Sends two types of emails:
  - Daily report  : profile changes, resume upload, jobs applied, errors
  - Error alert   : immediate notification when something crashes mid-run

Usage:
    svc = EmailService()
    svc.send_daily_report(report_dict)
    svc.send_error_alert("Morning session crashed", traceback_str)

report_dict keys (all optional — missing keys are shown as 'N/A'):
    date                str   — e.g. "2026-03-28"
    prev_headline       str
    new_headline        str
    headline_updated_at str   — e.g. "09:14:32"
    prev_summary        str
    new_summary         str
    summary_updated_at  str   — e.g. "09:27:05"
    resume_path         str | None  — local path to attach
    resume_uploaded_at  str   — e.g. "09:02:11"
    applied_jobs        list[dict]  — each: {title, company, url, combined_score, applied_at}
    errors              list[str]
"""

import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from config.settings import GMAIL_APP_PASSWORD, NAUKRI_EMAIL, REPORT_EMAIL

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


class EmailService:
    def __init__(self):
        self._from     = NAUKRI_EMAIL
        self._to       = REPORT_EMAIL
        self._password = GMAIL_APP_PASSWORD

    # ── Public ────────────────────────────────────────────────────────────────

    def send_daily_report(self, report: dict):
        """Send the end-of-day summary email."""
        if not self._configured():
            logger.warning("Email not configured — skipping daily report")
            return

        date_str     = report.get("date", "")
        subject      = f"Naukri Daily Report — {date_str}"
        html         = self._build_report_html(report)
        resume_path  = report.get("resume_path")

        msg = self._base_message(subject)
        msg.attach(MIMEText(html, "html"))

        if resume_path and Path(resume_path).is_file():
            self._attach_pdf(msg, resume_path)

        self._send(msg)
        logger.info("Daily report sent to %s", self._to)

    def send_error_alert(self, context: str, error: str):
        """Send an immediate error notification."""
        if not self._configured():
            logger.warning("Email not configured — skipping error alert")
            return

        subject = f"[Naukri Bot ERROR] {context}"
        html = f"""
        <html><body>
        <h2 style="color:#c0392b;">Error in Naukri Automation</h2>
        <p><strong>Context:</strong> {_esc(context)}</p>
        <pre style="background:#f8f8f8;padding:12px;border-left:4px solid #c0392b;
                    font-size:13px;white-space:pre-wrap;">{_esc(error)}</pre>
        </body></html>
        """
        msg = self._base_message(subject)
        msg.attach(MIMEText(html, "html"))
        self._send(msg)
        logger.info("Error alert sent: %s", context)

    # ── Private ───────────────────────────────────────────────────────────────

    def _configured(self) -> bool:
        return bool(self._password and self._from and self._to)

    def _base_message(self, subject: str) -> MIMEMultipart:
        msg = MIMEMultipart("mixed")
        msg["From"]    = self._from
        msg["To"]      = self._to
        msg["Subject"] = subject
        return msg

    def _send(self, msg: MIMEMultipart):
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.login(self._from, self._password)
                server.sendmail(self._from, self._to, msg.as_string())
        except Exception as e:
            logger.error("Failed to send email: %s", e)

    @staticmethod
    def _attach_pdf(msg: MIMEMultipart, path: str):
        with open(path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
            part.add_header(
                "Content-Disposition", "attachment",
                filename=Path(path).name,
            )
            msg.attach(part)

    @staticmethod
    def _build_report_html(r: dict) -> str:
        date_str             = _esc(r.get("date", ""))
        prev_headline        = _esc(r.get("prev_headline") or "N/A")
        new_headline         = _esc(r.get("new_headline")  or "N/A")
        headline_updated_at  = _esc(r.get("headline_updated_at") or "")
        prev_summary         = _esc(r.get("prev_summary")  or "N/A")
        new_summary          = _esc(r.get("new_summary")   or "N/A")
        summary_updated_at   = _esc(r.get("summary_updated_at") or "")
        resume_uploaded_at   = _esc(r.get("resume_uploaded_at") or "")
        resume_note          = "Attached to this email." if r.get("resume_path") else "Uploaded to Naukri (no local copy)."
        if resume_uploaded_at:
            resume_note += f"&nbsp; <span style='color:#888;font-size:13px'>({resume_uploaded_at})</span>"
        applied_jobs  = r.get("applied_jobs", [])
        errors        = r.get("errors", [])

        headline_ts_html = (
            f"&nbsp;<span style='color:#888;font-size:12px;font-weight:normal'>updated at {headline_updated_at}</span>"
            if headline_updated_at else ""
        )
        summary_ts_html = (
            f"&nbsp;<span style='color:#888;font-size:12px;font-weight:normal'>updated at {summary_updated_at}</span>"
            if summary_updated_at else ""
        )

        # Jobs table rows
        job_rows = ""
        for i, job in enumerate(applied_jobs, 1):
            score = job.get("combined_score")
            score_str = f"{score:.1f}" if score is not None else "—"
            url   = _esc(job.get("url", ""))
            title = _esc(job.get("title", ""))
            co    = _esc(job.get("company", ""))
            raw_ts = job.get("applied_at", "")
            # applied_at is stored as ISO datetime — show only HH:MM:SS
            if raw_ts and "T" in raw_ts:
                time_str = raw_ts.split("T")[1][:8]
            elif raw_ts:
                time_str = raw_ts
            else:
                time_str = "—"
            job_rows += f"""
            <tr style="background:{'#f9f9f9' if i%2==0 else '#fff'}">
                <td style="{_td}">{i}</td>
                <td style="{_td}"><a href="{url}">{title}</a></td>
                <td style="{_td}">{co}</td>
                <td style="{_td};text-align:center">{score_str}</td>
                <td style="{_td};text-align:center;color:#555;font-size:13px">{time_str}</td>
            </tr>"""

        if not job_rows:
            job_rows = f'<tr><td colspan="5" style="{_td};color:#888;text-align:center">No jobs applied today</td></tr>'

        # Errors section
        errors_html = ""
        if errors:
            error_items = "".join(
                f'<li style="margin-bottom:6px"><pre style="margin:0;white-space:pre-wrap">{_esc(e)}</pre></li>'
                for e in errors
            )
            errors_html = f"""
            <h2 style="{_h2};color:#c0392b;">Errors / Warnings</h2>
            <ul style="padding-left:20px">{error_items}</ul>
            """

        return f"""
        <html><body style="font-family:Arial,sans-serif;color:#333;max-width:800px;margin:auto;padding:24px">
        <h1 style="color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:8px">
            Naukri Daily Report — {date_str}
        </h1>

        <h2 style="{_h2}">Resume Headline{headline_ts_html}</h2>
        <table style="{_table}">
            <tr><td style="{_label}">Before</td><td style="{_td}">{prev_headline}</td></tr>
            <tr style="background:#f9f9f9"><td style="{_label}">After</td>
                <td style="{_td};color:#27ae60"><strong>{new_headline}</strong></td></tr>
        </table>

        <h2 style="{_h2}">Profile Summary{summary_ts_html}</h2>
        <table style="{_table}">
            <tr><td style="{_label};vertical-align:top">Before</td>
                <td style="{_td};white-space:pre-wrap">{prev_summary}</td></tr>
            <tr style="background:#f9f9f9">
                <td style="{_label};vertical-align:top">After</td>
                <td style="{_td};white-space:pre-wrap;color:#27ae60"><strong>{new_summary}</strong></td></tr>
        </table>

        <h2 style="{_h2}">Resume Upload</h2>
        <p style="margin:4px 0 16px">{resume_note}</p>

        <h2 style="{_h2}">Jobs Applied Today ({len(applied_jobs)})</h2>
        <table style="{_table};border-collapse:collapse;width:100%">
            <thead>
                <tr style="background:#3498db;color:#fff">
                    <th style="{_th}">#</th>
                    <th style="{_th}">Title</th>
                    <th style="{_th}">Company</th>
                    <th style="{_th}">Score</th>
                    <th style="{_th}">Time Applied</th>
                </tr>
            </thead>
            <tbody>{job_rows}</tbody>
        </table>

        {errors_html}

        <p style="margin-top:32px;font-size:12px;color:#aaa">
            Sent by PyNaurkiAutomation &nbsp;|&nbsp; {date_str}
        </p>
        </body></html>
        """


# ── Inline CSS constants (keeps the f-string readable) ────────────────────────
_h2    = "color:#2c3e50;margin-top:28px;margin-bottom:8px;font-size:16px"
_table = "border:1px solid #ddd;border-radius:6px;overflow:hidden;margin-bottom:16px;width:100%"
_label = "padding:10px 14px;font-weight:bold;width:80px;background:#ecf0f1"
_td    = "padding:10px 14px"
_th    = "padding:10px 14px;text-align:left;font-weight:600"


def _esc(text: str) -> str:
    """Minimal HTML escaping."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
