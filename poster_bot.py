#!/usr/bin/env python3
"""
poster_bot.py - Daily posting agent for X (Twitter).

What it does:
  * Reads drafted posts from config/content_queue.json
  * Publishes TEXT-ONLY posts through the X API v2 (via Tweepy)
  * Runs at fixed times every day (default 08:00, 13:00, 20:00)
  * Moves any post containing a link to a "manual_queue" (links cost much
    more on the pay-per-use API, so you post those yourself)
  * Tracks spend and stops when the monthly budget cap would be exceeded

Usage:
  python poster_bot.py            # start the scheduler (keeps running)
  python poster_bot.py --once     # publish ONE post right now and exit
  python poster_bot.py --check    # validate config/credentials and exit
"""

import argparse
import json
import logging
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import pytz
import schedule
from dotenv import load_dotenv

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
LOGS_DIR = BASE_DIR / "logs"
QUEUE_FILE = CONFIG_DIR / "content_queue.json"
QUEUE_TEMPLATE = CONFIG_DIR / "content_queue.example.json"
STRATEGY_FILE = CONFIG_DIR / "strategy_config.json"
TEXT_LOG = LOGS_DIR / "posts.log"

load_dotenv(BASE_DIR / ".env")

# --------------------------------------------------------------------------
# Settings (from .env, with safe defaults)
# --------------------------------------------------------------------------
POST_TIMES = [t.strip() for t in os.getenv("POST_TIMES", "08:00,13:00,20:00").split(",") if t.strip()]
TIMEZONE = os.getenv("TIMEZONE", "Europe/London")
MAX_POSTS_PER_DAY = int(os.getenv("MAX_POSTS_PER_DAY", "3"))
MONTHLY_BUDGET_USD = float(os.getenv("MONTHLY_BUDGET_USD", "3.33"))
COST_PER_POST_USD = float(os.getenv("COST_PER_POST_USD", "0.015"))
DRY_RUN = os.getenv("DRY_RUN", "false").strip().lower() in ("1", "true", "yes")
MAX_TWEET_CHARS = 280

# Detects http(s) links, www. links and bare domains such as "example.com/page"
URL_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+|\b[a-z0-9-]+\.(com|net|org|io|co|ly|me|app|dev|info|shop|store|link)\b(/\S*)?)",
    re.IGNORECASE,
)

# --------------------------------------------------------------------------
# Logging: console + logs/posts.log
# --------------------------------------------------------------------------
LOGS_DIR.mkdir(exist_ok=True)
logger = logging.getLogger("poster_bot")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    for handler in (logging.StreamHandler(sys.stdout), logging.FileHandler(TEXT_LOG, encoding="utf-8")):
        handler.setFormatter(fmt)
        logger.addHandler(handler)


# --------------------------------------------------------------------------
# Helpers: time, JSON files
# --------------------------------------------------------------------------
def tz():
    return pytz.timezone(TIMEZONE)


def now_local() -> datetime:
    return datetime.now(tz())


def read_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data) -> None:
    """Write atomically so a crash never leaves a half-written file."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def load_queue() -> dict:
    """Load the queue; on first run, create it from the example template."""
    if not QUEUE_FILE.exists():
        if QUEUE_TEMPLATE.exists():
            shutil.copy(QUEUE_TEMPLATE, QUEUE_FILE)
            logger.info("Created %s from the example template.", QUEUE_FILE.name)
        else:
            write_json(QUEUE_FILE, {"queue": [], "manual_queue": [], "published": []})
    data = read_json(QUEUE_FILE, {})
    # Make sure every expected key exists
    data.setdefault("account_handle", "@YOUR_HANDLE")
    data.setdefault("last_updated", "")
    data.setdefault("total_spend_usd", 0.0)
    data.setdefault("posts_today", 0)
    data.setdefault("last_post_date", "")
    data.setdefault("error_402_week", False)
    for key in ("queue", "manual_queue", "published"):
        data.setdefault(key, [])
    return data


def save_queue(data: dict) -> None:
    data["last_updated"] = now_local().isoformat(timespec="seconds")
    write_json(QUEUE_FILE, data)


def monthly_log_path(dt: datetime) -> Path:
    return LOGS_DIR / f"posts_{dt:%Y-%m}.json"


def append_monthly_log(entry: dict) -> None:
    path = monthly_log_path(now_local())
    entries = read_json(path, [])
    entries.append(entry)
    write_json(path, entries)


def monthly_spend(dt: datetime = None) -> float:
    """Sum of costs logged in the given month (defaults to current month)."""
    entries = read_json(monthly_log_path(dt or now_local()), [])
    return round(sum(e.get("cost_usd", 0.0) for e in entries), 4)


# --------------------------------------------------------------------------
# Content rules
# --------------------------------------------------------------------------
def post_texts(item: dict) -> list:
    """A post is either a single 'text' or a 'thread' (list of texts)."""
    if item.get("type") == "thread" and isinstance(item.get("thread"), list):
        return [t for t in item["thread"] if str(t).strip()]
    return [item.get("text", "")]


def has_link(item: dict) -> bool:
    return any(URL_PATTERN.search(t or "") for t in post_texts(item))


def route_manual_posts(data: dict) -> None:
    """Move posts with links (or too long) out of the auto queue."""
    keep = []
    for item in data["queue"]:
        reason = None
        if has_link(item) or item.get("media"):
            reason = "contains_link_or_media"
        elif any(len(t) > MAX_TWEET_CHARS for t in post_texts(item)):
            reason = "too_long"
        elif not any(t.strip() for t in post_texts(item)):
            reason = "empty_text"
        if reason:
            item["manual_reason"] = reason
            item["moved_at"] = now_local().isoformat(timespec="seconds")
            data["manual_queue"].append(item)
            logger.info("Moved %s to manual_queue (%s).", item.get("id", "?"), reason)
        else:
            keep.append(item)
    data["queue"] = keep


# --------------------------------------------------------------------------
# X API
# --------------------------------------------------------------------------
class PaymentRequired(Exception):
    """Raised when the X API answers HTTP 402 (no credit / plan limit)."""


def get_client():
    import tweepy  # imported lazily so --check gives a clear error

    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    missing = [k for k in required if not os.getenv(k) or os.getenv(k, "").startswith("your_")]
    if missing:
        raise RuntimeError(f"Missing credentials in .env: {', '.join(missing)}")
    return tweepy.Client(
        bearer_token=os.getenv("X_BEARER_TOKEN") or None,
        consumer_key=os.getenv("X_API_KEY"),
        consumer_secret=os.getenv("X_API_SECRET"),
        access_token=os.getenv("X_ACCESS_TOKEN"),
        access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
    )


def publish(texts: list) -> list:
    """Publish one tweet or a thread. Returns the list of tweet IDs."""
    if DRY_RUN:
        logger.info("[DRY RUN] Would publish %d tweet(s): %r", len(texts), texts[0][:60])
        return [f"dryrun-{int(time.time())}-{i}" for i in range(len(texts))]

    import tweepy

    client = get_client()
    ids, reply_to = [], None
    for text in texts:
        try:
            resp = client.create_tweet(text=text, in_reply_to_tweet_id=reply_to)
        except tweepy.errors.HTTPException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 402:
                raise PaymentRequired(str(exc)) from exc
            raise
        reply_to = resp.data["id"]
        ids.append(reply_to)
    return ids


# --------------------------------------------------------------------------
# The scheduled job
# --------------------------------------------------------------------------
def run_post_job() -> None:
    """Publish the next post in the queue, respecting all limits."""
    data = load_queue()
    today = now_local().date().isoformat()

    # Reset the daily counter at midnight (first run of a new day)
    if data["last_post_date"] != today:
        data["posts_today"] = 0
        data["last_post_date"] = today

    route_manual_posts(data)

    if data["posts_today"] >= MAX_POSTS_PER_DAY:
        logger.info("Daily limit reached (%d). Skipping.", MAX_POSTS_PER_DAY)
        save_queue(data)
        return

    if not data["queue"]:
        logger.warning("Queue is empty - nothing to post. Add posts to %s.", QUEUE_FILE.name)
        save_queue(data)
        return

    item = data["queue"][0]
    texts = post_texts(item)
    cost = round(COST_PER_POST_USD * len(texts), 4)
    spent = monthly_spend()

    if spent + cost > MONTHLY_BUDGET_USD:
        logger.error("Budget cap reached: $%.3f spent of $%.2f. Posting stopped.", spent, MONTHLY_BUDGET_USD)
        data["error_402_week"] = True
        append_monthly_log({"id": item.get("id"), "status": "budget_exceeded",
                            "timestamp": now_local().isoformat(timespec="seconds"), "cost_usd": 0.0})
        save_queue(data)
        return

    try:
        tweet_ids = publish(texts)
    except PaymentRequired as exc:
        logger.error("X API returned 402 Payment Required: %s", exc)
        data["error_402_week"] = True
        append_monthly_log({"id": item.get("id"), "status": "error_402",
                            "timestamp": now_local().isoformat(timespec="seconds"), "cost_usd": 0.0})
        save_queue(data)
        return
    except Exception as exc:  # network errors, auth errors, duplicates...
        logger.error("Failed to publish %s: %s", item.get("id"), exc)
        append_monthly_log({"id": item.get("id"), "status": "error",
                            "error": str(exc)[:300],
                            "timestamp": now_local().isoformat(timespec="seconds"), "cost_usd": 0.0})
        save_queue(data)
        return

    # Success: move item from queue to published and update counters
    stamp = now_local().isoformat(timespec="seconds")
    cost = 0.0 if DRY_RUN else cost  # simulated posts cost nothing
    data["queue"].pop(0)
    item.update({"published_at": stamp, "tweet_ids": tweet_ids, "cost_usd": cost, "dry_run": DRY_RUN})
    data["published"].append(item)
    data["posts_today"] += 1
    data["total_spend_usd"] = round(data["total_spend_usd"] + cost, 4)
    save_queue(data)

    append_monthly_log({"id": item.get("id"), "status": "published", "timestamp": stamp,
                        "pillar": item.get("pillar"), "type": item.get("type", "single"),
                        "tweet_ids": tweet_ids, "cost_usd": cost, "dry_run": DRY_RUN,
                        "text": texts[0][:280]})
    logger.info("Published %s (%d tweet(s), $%.3f). Month: $%.3f / $%.2f. Left in queue: %d.",
                item.get("id"), len(texts), cost, spent + cost, MONTHLY_BUDGET_USD, len(data["queue"]))


# --------------------------------------------------------------------------
# Config check
# --------------------------------------------------------------------------
def check_setup() -> bool:
    ok = True
    try:
        tz()
    except pytz.UnknownTimeZoneError:
        logger.error("Unknown TIMEZONE '%s' (example: Europe/London, America/New_York).", TIMEZONE)
        ok = False
    for t in POST_TIMES:
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t):
            logger.error("Invalid time in POST_TIMES: '%s' (use HH:MM).", t)
            ok = False
    if not STRATEGY_FILE.exists():
        logger.warning("%s not found (optional, used for reports).", STRATEGY_FILE.name)
    data = load_queue()
    logger.info("Queue: %d post(s) ready, %d in manual_queue, %d published.",
                len(data["queue"]), len(data["manual_queue"]), len(data["published"]))
    if DRY_RUN:
        logger.info("DRY_RUN is ON - no real posts will be sent.")
    else:
        try:
            me = get_client().get_me()
            logger.info("Authenticated on X as @%s.", me.data.username)
        except Exception as exc:
            logger.error("X authentication failed: %s", exc)
            ok = False
    logger.info("Setup check %s.", "PASSED" if ok else "FAILED")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated text-only poster for X (Twitter).")
    parser.add_argument("--once", action="store_true", help="publish one post now and exit")
    parser.add_argument("--check", action="store_true", help="validate setup and exit")
    args = parser.parse_args()

    if args.check:
        sys.exit(0 if check_setup() else 1)
    if args.once:
        run_post_job()
        return

    for t in POST_TIMES:
        schedule.every().day.at(t, TIMEZONE).do(run_post_job)
    logger.info("Scheduler started. Posting at %s (%s). DRY_RUN=%s. Press Ctrl+C to stop.",
                ", ".join(POST_TIMES), TIMEZONE, DRY_RUN)
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
