#!/usr/bin/env python3
"""
weekly_report.py - Weekly Markdown report for the posting bot.

Every Monday (default 09:00) it summarizes the previous 7 days:
  * posts published vs target (MAX_POSTS_PER_DAY x 7)
  * posts waiting in the manual queue (links / media to post by hand)
  * budget: weekly spend, monthly spend vs cap, total, end-of-month projection
  * RED ALERT on any 402 error or when spend is above 80% of the cap
  * breakdown by content pillar

The report is saved to logs/weekly_report_YYYY-WNN.md and can optionally be
emailed (fill in the SMTP_* variables in .env).

Usage:
  python weekly_report.py         # start the weekly scheduler (keeps running)
  python weekly_report.py --now   # generate the report right now and exit
"""

import argparse
import calendar
import os
import smtplib
import time
from collections import Counter
from datetime import datetime, timedelta
from email.message import EmailMessage

import schedule

from poster_bot import (
    LOGS_DIR, MAX_POSTS_PER_DAY, MONTHLY_BUDGET_USD, STRATEGY_FILE, TIMEZONE,
    load_queue, logger, monthly_log_path, monthly_spend, now_local, read_json, save_queue,
)

WEEKLY_REPORT_TIME = os.getenv("WEEKLY_REPORT_TIME", "09:00")
ALERT_THRESHOLD = 0.80  # alert when monthly spend > 80% of the cap


def entries_between(start, end) -> list:
    """Collect log entries with start <= timestamp < end (may span 2 months)."""
    months = {monthly_log_path(start), monthly_log_path(end - timedelta(seconds=1))}
    result = []
    for path in months:
        for e in read_json(path, []):
            try:
                ts = datetime.fromisoformat(e["timestamp"])
            except (KeyError, ValueError):
                continue
            if ts.tzinfo is None:
                ts = start.tzinfo.localize(ts) if hasattr(start.tzinfo, "localize") else ts.replace(tzinfo=start.tzinfo)
            if start <= ts < end:
                result.append(e)
    return result


def pillar_names() -> dict:
    strategy = read_json(STRATEGY_FILE, {})
    return {p.get("id"): f"{p.get('emoji', '')} {p.get('name', '')}".strip()
            for p in strategy.get("content_pillars", [])}


def build_report() -> tuple:
    """Return (filename, markdown_text, has_alert)."""
    now = now_local()
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=7)
    iso_year, iso_week, _ = start.isocalendar()

    entries = entries_between(start, end)
    published = [e for e in entries if e.get("status") == "published"]
    errors_402 = [e for e in entries if e.get("status") in ("error_402", "budget_exceeded")]
    other_errors = [e for e in entries if e.get("status") == "error"]

    data = load_queue()
    target = MAX_POSTS_PER_DAY * 7
    weekly_spend = round(sum(e.get("cost_usd", 0.0) for e in published), 4)
    month_spend = monthly_spend(now)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    projection = round(month_spend / max(now.day, 1) * days_in_month, 3)
    pct_cap = (month_spend / MONTHLY_BUDGET_USD * 100) if MONTHLY_BUDGET_USD else 0

    alerts = []
    if errors_402 or data.get("error_402_week"):
        alerts.append("A **402 / budget-cap** event happened: posting was stopped. Check your X API credits.")
    if MONTHLY_BUDGET_USD and month_spend > ALERT_THRESHOLD * MONTHLY_BUDGET_USD:
        alerts.append(f"Monthly spend is at **{pct_cap:.0f}%** of the cap (> {ALERT_THRESHOLD:.0%}).")
    if projection > MONTHLY_BUDGET_USD:
        alerts.append(f"Projected month spend **${projection:.2f}** exceeds the cap of ${MONTHLY_BUDGET_USD:.2f}.")

    names = pillar_names()
    pillars = Counter(e.get("pillar") for e in published)

    lines = [
        f"# Weekly Report - {iso_year}-W{iso_week:02d}",
        "",
        f"Period: **{start:%Y-%m-%d}** to **{(end - timedelta(days=1)):%Y-%m-%d}** ({TIMEZONE})  ",
        f"Account: {data.get('account_handle', '@YOUR_HANDLE')}  ",
        f"Generated: {now:%Y-%m-%d %H:%M}",
        "",
    ]
    if alerts:
        lines += ["## 🔴 RED ALERT", ""] + [f"- {a}" for a in alerts] + [""]

    lines += [
        "## 📊 Posts",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Published this week | {len(published)} / {target} ({(len(published) / target * 100 if target else 0):.0f}%) |",
        f"| Failed attempts | {len(other_errors)} |",
        f"| Still in auto queue | {len(data['queue'])} |",
        f"| Waiting in manual queue | {len(data['manual_queue'])} |",
        "",
        "## 💰 Budget",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Spend this week | ${weekly_spend:.3f} |",
        f"| Spend this month | ${month_spend:.3f} / ${MONTHLY_BUDGET_USD:.2f} ({pct_cap:.0f}%) |",
        f"| Projected end of month | ${projection:.3f} |",
        f"| Cumulative total | ${data.get('total_spend_usd', 0.0):.3f} |",
        "",
        "## 🧱 Content pillars (this week)",
        "",
    ]
    if pillars:
        lines += ["| Pillar | Posts |", "|---|---|"]
        for pid, count in sorted(pillars.items(), key=lambda kv: -kv[1]):
            lines.append(f"| {names.get(pid, f'Pillar {pid}')} | {count} |")
    else:
        lines.append("_No posts published this week._")

    lines += ["", "## ✋ Manual queue (post these by hand)", ""]
    if data["manual_queue"]:
        for item in data["manual_queue"]:
            text = (item.get("text") or " / ".join(item.get("thread", [])))[:120].replace("\n", " ")
            lines.append(f"- `{item.get('id', '?')}` ({item.get('manual_reason', 'manual')}): {text}")
    else:
        lines.append("_Empty._")

    lines += ["", "---", "_Generated automatically by twitter-bot-scheduler._", ""]
    filename = LOGS_DIR / f"weekly_report_{iso_year}-W{iso_week:02d}.md"
    return filename, "\n".join(lines), bool(alerts)


def send_email(subject: str, body: str) -> None:
    host, to = os.getenv("SMTP_HOST"), os.getenv("REPORT_EMAIL_TO")
    if not host or not to:
        return  # email is optional
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("SMTP_USER") or to
    msg["To"] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=30) as smtp:
            smtp.starttls()
            if os.getenv("SMTP_USER"):
                smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD", ""))
            smtp.send_message(msg)
        logger.info("Weekly report emailed to %s.", to)
    except Exception as exc:
        logger.error("Could not send report email: %s", exc)


def run_report_job() -> None:
    filename, text, has_alert = build_report()
    filename.write_text(text, encoding="utf-8")
    logger.info("Weekly report saved to %s%s", filename.name, " (RED ALERT)" if has_alert else "")
    send_email(("🔴 " if has_alert else "") + f"X bot weekly report - {filename.stem}", text)

    # Reset the weekly 402 flag once it has been reported
    data = load_queue()
    if data.get("error_402_week"):
        data["error_402_week"] = False
        save_queue(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly report for twitter-bot-scheduler.")
    parser.add_argument("--now", action="store_true", help="generate the report now and exit")
    args = parser.parse_args()

    if args.now:
        run_report_job()
        return

    schedule.every().monday.at(WEEKLY_REPORT_TIME, TIMEZONE).do(run_report_job)
    logger.info("Weekly report scheduled every Monday at %s (%s). Press Ctrl+C to stop.",
                WEEKLY_REPORT_TIME, TIMEZONE)
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Report scheduler stopped.")


if __name__ == "__main__":
    main()
