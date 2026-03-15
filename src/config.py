from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
STATE_FILE = DATA_DIR / "state.json"
FOREX_FACTORY_ICS_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.ics"


def _desktop_candidates() -> list[Path]:
    home = Path.home()
    userprofile = Path(os.environ.get("USERPROFILE", home))
    return [
        Path(os.environ["DISCORD_WEBHOOK_FILE"])
        if os.environ.get("DISCORD_WEBHOOK_FILE")
        else None,
        userprofile / "Desktop" / "Discord WEBHOOK.txt",
        home / "Desktop" / "Discord WEBHOOK.txt",
    ]


def _read_webhook_from_file() -> str | None:
    for candidate in _desktop_candidates():
        if candidate is None or not candidate.exists():
            continue
        value = candidate.read_text(encoding="utf-8").strip()
        if value:
            return value
    return None


def _read_webhook_url(required: bool) -> str | None:
    value = (
        os.environ.get("DISCORD_WEBHOOK_URL")
        or os.environ.get("DISCORD_WEBHOOK")
        or _read_webhook_from_file()
    )
    if value:
        return value.strip()
    if required:
        raise RuntimeError(
            "Discord webhook not found. Set DISCORD_WEBHOOK_URL or create "
            "'Discord WEBHOOK.txt' on the Desktop."
        )
    return None


@dataclass(frozen=True)
class Settings:
    webhook_url: str | None
    timezone_name: str
    alert_lead_minutes: int
    alert_window_minutes: int
    calendar_refresh_hours: int
    request_timeout_seconds: int
    mention_text: str
    dry_run: bool

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)


def load_settings(*, dry_run: bool = False) -> Settings:
    timezone_name = os.environ.get("APP_TIMEZONE", "Pacific/Tahiti").strip()
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError(f"Unknown timezone: {timezone_name}") from exc

    alert_lead_minutes = int(os.environ.get("ALERT_LEAD_MINUTES", "30"))
    alert_window_minutes = int(os.environ.get("ALERT_WINDOW_MINUTES", "7"))
    calendar_refresh_hours = int(os.environ.get("CALENDAR_REFRESH_HOURS", "12"))
    request_timeout_seconds = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30"))

    if alert_lead_minutes <= 0:
        raise RuntimeError("ALERT_LEAD_MINUTES must be > 0.")
    if alert_window_minutes < 1:
        raise RuntimeError("ALERT_WINDOW_MINUTES must be >= 1.")
    if calendar_refresh_hours < 1:
        raise RuntimeError("CALENDAR_REFRESH_HOURS must be >= 1.")

    return Settings(
        webhook_url=_read_webhook_url(required=not dry_run),
        timezone_name=timezone_name,
        alert_lead_minutes=alert_lead_minutes,
        alert_window_minutes=alert_window_minutes,
        calendar_refresh_hours=calendar_refresh_hours,
        request_timeout_seconds=request_timeout_seconds,
        mention_text=os.environ.get("DISCORD_ALERT_MENTION", "@everyone").strip(),
        dry_run=dry_run,
    )
