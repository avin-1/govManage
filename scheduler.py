"""
scheduler.py
────────────
APScheduler-based weekly email dispatcher for govManage.

Environment variables:
    EMAIL_WEEKLY_DAY   Day of the week for dispatch   (default: "monday")
    EMAIL_WEEKLY_TIME  HH:MM UTC time                 (default: "08:00")
    EMAIL_RECIPIENTS   Comma-separated recipients     (used by send_weekly_report)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_scheduler: Optional[Any] = None  # BackgroundScheduler instance


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def get_schedule_config() -> Dict[str, str]:
    day = os.getenv("EMAIL_WEEKLY_DAY", "monday").strip().lower()
    time_str = os.getenv("EMAIL_WEEKLY_TIME", "08:00").strip()
    try:
        hour, minute = [int(x) for x in time_str.split(":")[:2]]
    except ValueError:
        hour, minute = 8, 0
    return {"day_of_week": day, "hour": str(hour), "minute": str(minute)}


# ---------------------------------------------------------------------------
# Scheduled job
# ---------------------------------------------------------------------------

def _run_weekly_report_job() -> None:
    """Called by APScheduler on the configured schedule."""
    logger.info("[scheduler] Running scheduled weekly GRC report job")
    try:
        from email_service import send_weekly_report
        from database import db

        result = send_weekly_report()
        status = "sent" if result.get("ok") else "failed"
        error = result.get("error", "")

        # Persist last-run metadata to MongoDB
        db.db["email_dispatch_log"].insert_one({
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "trigger": "scheduled",
            "status": status,
            "error": error,
            "recipients": result.get("recipients", []),
        })

        if result.get("ok"):
            logger.info("[scheduler] Weekly report sent successfully to %s", result.get("recipients"))
        else:
            logger.error("[scheduler] Weekly report FAILED: %s", error)

    except Exception as exc:
        logger.exception("[scheduler] Unhandled error in weekly report job: %s", exc)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def start_scheduler() -> bool:
    """
    Start the APScheduler BackgroundScheduler with the weekly email job.
    Returns True if started, False if APScheduler is unavailable.
    """
    global _scheduler

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("[scheduler] APScheduler not installed — weekly email dispatch disabled.")
        return False

    if _scheduler is not None and _scheduler.running:
        logger.info("[scheduler] Already running.")
        return True

    cfg = get_schedule_config()

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_weekly_report_job,
        trigger=CronTrigger(
            day_of_week=cfg["day_of_week"],
            hour=int(cfg["hour"]),
            minute=int(cfg["minute"]),
            timezone="UTC",
        ),
        id="weekly_grc_report",
        name="Weekly GRC Report Email",
        replace_existing=True,
    )

    try:
        _scheduler.start()
        logger.info(
            "[scheduler] Started — weekly report scheduled for %s at %s:%s UTC",
            cfg["day_of_week"], cfg["hour"], cfg["minute"]
        )
        return True
    except Exception as exc:
        logger.error("[scheduler] Failed to start: %s", exc)
        return False


def stop_scheduler() -> None:
    """Gracefully stop the scheduler if running."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] Stopped.")
    _scheduler = None


def get_scheduler_status() -> Dict[str, Any]:
    """Return a dict describing the current scheduler state."""
    cfg = get_schedule_config()
    running = _scheduler is not None and _scheduler.running

    next_run: Optional[str] = None
    if running and _scheduler:
        try:
            job = _scheduler.get_job("weekly_grc_report")
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()
        except Exception:
            pass

    return {
        "running": running,
        "day_of_week": cfg["day_of_week"],
        "hour": cfg["hour"],
        "minute": cfg["minute"],
        "next_run": next_run,
    }
