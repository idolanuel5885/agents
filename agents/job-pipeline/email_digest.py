"""
Daily email digest for the job pipeline.

Queries new jobs from the DB (passed filters, seen in last 25 hours),
scores each against the candidate profile using Claude Haiku,
and sends a formatted HTML email via Resend.

Called from run.py with --send-email flag.
"""

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import anthropic
import httpx

PROFILE_PATH = Path(__file__).parent / "candidate_profile.txt"
TO_EMAIL     = "idolanuel@gmail.com"
FROM_EMAIL   = "onboarding@resend.dev"   # update once you add a domain in Resend


# ---------------------------------------------------------------------------
# DB query
# ---------------------------------------------------------------------------

def get_new_jobs(db_path: str) -> list[dict]:
    """Return jobs first seen in the last 25 hours that passed filters."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT
                j.id, j.title, j.company, j.location, j.is_remote,
                j.salary_min, j.salary_max, j.salary_raw,
                j.apply_url, j.source, j.date_posted,
                j.company_size_resolved, j.company_size_raw,
                j.description_raw,
                l.hiring_manager_name, l.hiring_manager_title,
                l.email AS hm_email, l.email_confidence, l.linkedin_url
            FROM jobs j
            LEFT JOIN leads l ON j.id = l.job_id
            WHERE j.first_seen >= datetime('now', '-25 hours')
              AND j.passed_filters = 1
            ORDER BY j.first_seen DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_one(job: dict, profile: str, client: anthropic.Anthropic) -> tuple[int, str]:
    description = (job.get("description_raw") or "")[:700]
    size = job.get("company_size_resolved") or job.get("company_size_raw") or "unknown"
    prompt = (
        "Score this job's fit for the candidate described in the profile. "
        "Reply with JSON only, no prose: {\"score\": <1-10>, \"reason\": \"<one sentence>\"}\n\n"
        f"CANDIDATE PROFILE:\n{profile}\n\n"
        f"JOB:\n"
        f"Title: {job.get('title', '')}\n"
        f"Company: {job.get('company', '')}\n"
        f"Location: {job.get('location') or ('Remote' if job.get('is_remote') else 'Not specified')}\n"
        f"Company size: {size} employees\n"
        f"Description: {description}"
    )
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return max(1, min(10, int(data.get("score", 5)))), str(data.get("reason", ""))
    except Exception:
        pass
    return 5, ""


def score_jobs(jobs: list[dict], profile: str, client: anthropic.Anthropic) -> list[dict]:
    print(f"  Scoring {len(jobs)} jobs...", flush=True)
    for i, job in enumerate(jobs, 1):
        job["fit_score"], job["fit_reason"] = _score_one(job, profile, client)
        if i % 5 == 0:
            print(f"  {i}/{len(jobs)} scored", flush=True)
    return sorted(jobs, key=lambda j: j.get("fit_score", 0), reverse=True)


# ---------------------------------------------------------------------------
# Email HTML
# ---------------------------------------------------------------------------

def _fmt_salary(job: dict) -> str:
    lo, hi = job.get("salary_min"), job.get("salary_max")
    if lo and hi:
        return f"${int(lo):,}–${int(hi):,}"
    if lo:
        return f"${int(lo):,}+"
    return job.get("salary_raw") or "—"


def _score_pill(score: int) -> str:
    color = "#22c55e" if score >= 8 else "#f59e0b" if score >= 6 else "#94a3b8"
    return (
        f'<span style="background:{color};color:#fff;padding:3px 10px;'
        f'border-radius:12px;font-weight:700;font-size:12px">{score}/10</span>'
    )


def _job_row(job: dict) -> str:
    title   = job.get("title", "")
    company = job.get("company", "")
    loc     = job.get("location") or ("Remote" if job.get("is_remote") else "—")
    url     = job.get("apply_url", "#")
    salary  = _fmt_salary(job)
    score   = job.get("fit_score", 0)
    reason  = job.get("fit_reason", "")
    source  = job.get("source", "")
    hm_name = job.get("hiring_manager_name") or ""
    hm_email= job.get("hm_email") or ""
    hm_conf = job.get("email_confidence")

    hm_cell = "—"
    if hm_name:
        hm_cell = hm_name
        if hm_email:
            conf_tag = (
                f' <span style="color:#f59e0b;font-size:10px">({hm_conf}%)</span>'
                if hm_conf and hm_conf < 70 else ""
            )
            hm_cell += f'<br><a href="mailto:{hm_email}" style="color:#6366f1;font-size:12px">{hm_email}</a>{conf_tag}'

    return f"""
<tr style="border-bottom:1px solid #f1f5f9">
  <td style="padding:12px 10px;min-width:220px">
    <a href="{url}" style="color:#4f46e5;font-weight:600;text-decoration:none;font-size:14px">{title}</a>
    {"<br><span style='color:#64748b;font-size:12px;line-height:1.4'>" + reason + "</span>" if reason else ""}
  </td>
  <td style="padding:12px 10px;color:#1e293b;font-size:13px;white-space:nowrap">{company}</td>
  <td style="padding:12px 10px;color:#64748b;font-size:13px">{loc}</td>
  <td style="padding:12px 10px;color:#64748b;font-size:13px;white-space:nowrap">{salary}</td>
  <td style="padding:12px 10px">{_score_pill(score)}</td>
  <td style="padding:12px 10px;font-size:12px;color:#475569;min-width:160px">{hm_cell}</td>
  <td style="padding:12px 10px;color:#94a3b8;font-size:11px">{source}</td>
</tr>"""


TABLE_HEADER = """
<table style="width:100%;border-collapse:collapse;font-family:-apple-system,sans-serif">
  <thead>
    <tr style="background:#f8fafc">
      <th style="padding:8px 10px;text-align:left;color:#94a3b8;font-size:11px;text-transform:uppercase;font-weight:600">Role</th>
      <th style="padding:8px 10px;text-align:left;color:#94a3b8;font-size:11px;text-transform:uppercase;font-weight:600">Company</th>
      <th style="padding:8px 10px;text-align:left;color:#94a3b8;font-size:11px;text-transform:uppercase;font-weight:600">Location</th>
      <th style="padding:8px 10px;text-align:left;color:#94a3b8;font-size:11px;text-transform:uppercase;font-weight:600">Salary</th>
      <th style="padding:8px 10px;text-align:left;color:#94a3b8;font-size:11px;text-transform:uppercase;font-weight:600">Fit</th>
      <th style="padding:8px 10px;text-align:left;color:#94a3b8;font-size:11px;text-transform:uppercase;font-weight:600">Hiring Manager</th>
      <th style="padding:8px 10px;text-align:left;color:#94a3b8;font-size:11px;text-transform:uppercase;font-weight:600">Source</th>
    </tr>
  </thead>
  <tbody>"""


def build_html(jobs: list[dict], pipeline_stats: dict) -> str:
    today      = datetime.now().strftime("%A, %B %-d")
    total      = len(jobs)
    top_jobs   = [j for j in jobs if j.get("fit_score", 0) >= 7]
    other_jobs = [j for j in jobs if j.get("fit_score", 0) < 7]

    found    = pipeline_stats.get("jobs_found", "—")
    new_ct   = pipeline_stats.get("jobs_new", total)
    enriched = pipeline_stats.get("enriched", "—")

    sheet_stats  = pipeline_stats.get("sheet_stats", {})
    sheet_error  = sheet_stats.get("error") if isinstance(sheet_stats, dict) else None
    sheet_new    = sheet_stats.get("new", "—") if isinstance(sheet_stats, dict) else "—"
    sheet_update = sheet_stats.get("updated", "—") if isinstance(sheet_stats, dict) else "—"

    sheet_banner = ""
    if sheet_error:
        sheet_banner = f"""
<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;
            padding:14px 18px;margin-bottom:20px;color:#991b1b;font-size:13px">
  <strong>⚠ Google Sheets export failed</strong><br>
  {sheet_error}<br>
  <span style="color:#b91c1c">Check that the service account has <strong>Editor</strong>
  access to the spreadsheet, and that GOOGLE_SHEET_ID / GOOGLE_SERVICE_ACCOUNT_JSON
  are set correctly in the cron service's environment variables.</span>
</div>"""

    stats_bar = f"""
<div style="display:flex;gap:40px;background:#f8fafc;border-radius:10px;padding:20px 24px;margin-bottom:28px">
  <div><div style="font-size:28px;font-weight:700;color:#1e293b">{total}</div>
       <div style="color:#64748b;font-size:13px">new jobs today</div></div>
  <div><div style="font-size:28px;font-weight:700;color:#22c55e">{len(top_jobs)}</div>
       <div style="color:#64748b;font-size:13px">strong matches (7+)</div></div>
  <div><div style="font-size:28px;font-weight:700;color:#94a3b8">{found}</div>
       <div style="color:#94a3b8;font-size:13px">total scraped</div></div>
  <div><div style="font-size:28px;font-weight:700;color:#94a3b8">{enriched}</div>
       <div style="color:#94a3b8;font-size:13px">contacts found</div></div>
  <div><div style="font-size:28px;font-weight:700;color:{'#ef4444' if sheet_error else '#94a3b8'}">{sheet_new if not sheet_error else '✗'}</div>
       <div style="color:#64748b;font-size:13px">added to sheet</div></div>
</div>"""

    top_section = ""
    if top_jobs:
        rows = "".join(_job_row(j) for j in top_jobs)
        top_section = f"""
<h2 style="font-size:16px;color:#1e293b;margin:0 0 10px">
  Strong Matches <span style="color:#22c55e">({len(top_jobs)})</span>
</h2>
{TABLE_HEADER}{rows}</tbody></table>"""

    other_section = ""
    if other_jobs:
        rows = "".join(_job_row(j) for j in other_jobs)
        other_section = f"""
<h2 style="font-size:15px;color:#64748b;margin:32px 0 10px">
  Other New Jobs ({len(other_jobs)})
</h2>
{TABLE_HEADER}{rows}</tbody></table>"""

    no_jobs_msg = ""
    if not jobs:
        no_jobs_msg = '<p style="color:#94a3b8;padding:24px 0">No new jobs passed filters today.</p>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             max-width:960px;margin:0 auto;padding:32px 24px;color:#1e293b;background:#fff">

  <div style="margin-bottom:24px">
    <h1 style="font-size:22px;margin:0;color:#0f172a">Job Pipeline</h1>
    <p style="color:#64748b;margin:4px 0 0;font-size:14px">{today}</p>
  </div>

  {sheet_banner}
  {stats_bar}
  {no_jobs_msg}
  {top_section}
  {other_section}

  <p style="color:#cbd5e1;font-size:11px;margin-top:40px;border-top:1px solid #f1f5f9;padding-top:16px">
    Scored by Claude Haiku against your candidate profile.
    Hiring manager data via Hunter.io.
  </p>
</body></html>"""


# ---------------------------------------------------------------------------
# Send via Resend
# ---------------------------------------------------------------------------

def send_email(html: str, subject: str) -> bool:
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        print("Warning: RESEND_API_KEY not set — skipping email", flush=True)
        return False
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json",
            },
            json={"from": FROM_EMAIL, "to": [TO_EMAIL], "subject": subject, "html": html},
            timeout=20,
        )
        if r.status_code in (200, 201):
            print(f"✓ Email sent → {TO_EMAIL}", flush=True)
            return True
        print(f"✗ Resend error {r.status_code}: {r.text}", flush=True)
        return False
    except Exception as e:
        print(f"✗ Email send failed: {e}", flush=True)
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_digest(db_path: str, pipeline_stats: dict | None = None):
    """Score new jobs and send the daily email digest."""
    stats = pipeline_stats or {}

    print("→ Building email digest...", flush=True)

    jobs = get_new_jobs(db_path)
    print(f"  {len(jobs)} new jobs found (passed filters, last 25h)", flush=True)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key and jobs:
        profile = (
            PROFILE_PATH.read_text()
            if PROFILE_PATH.exists()
            else "Product executive with 10+ years in B2B SaaS"
        )
        client = anthropic.Anthropic(api_key=api_key)
        jobs   = score_jobs(jobs, profile, client)
    elif jobs:
        print("  Warning: ANTHROPIC_API_KEY not set — sending without scores", flush=True)
        for j in jobs:
            j["fit_score"] = 0
            j["fit_reason"] = ""

    top   = len([j for j in jobs if j.get("fit_score", 0) >= 7])
    today = datetime.now().strftime("%b %-d")
    subject = f"Jobs — {len(jobs)} new today ({today}), {top} strong match{'es' if top != 1 else ''}"

    html = build_html(jobs, stats)
    send_email(html, subject)
