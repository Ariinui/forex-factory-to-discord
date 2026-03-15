from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar

from .config import FOREX_FACTORY_ICS_URL

IMPACT_RE = re.compile(r"impact:\s*(high|medium|low|none)", re.IGNORECASE)
KNOWN_CURRENCIES = {
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "AUD",
    "CAD",
    "CHF",
    "NZD",
    "CNY",
    "CNH",
    "SGD",
    "HKD",
    "NOK",
    "SEK",
    "DKK",
    "MXN",
    "ZAR",
    "BRL",
    "INR",
    "KRW",
    "TRY",
}
COUNTRY_TO_CURRENCY = {
    "US": "USD",
    "EU": "EUR",
    "EZ": "EUR",
    "UK": "GBP",
    "JN": "JPY",
    "JP": "JPY",
    "AU": "AUD",
    "CA": "CAD",
    "NZ": "NZD",
    "SZ": "CHF",
    "CH": "CNY",
    "HK": "HKD",
    "SG": "SGD",
    "NO": "NOK",
    "SE": "SEK",
    "DK": "DKK",
    "MX": "MXN",
    "ZA": "ZAR",
    "BR": "BRL",
    "IN": "INR",
    "KR": "KRW",
    "TR": "TRY",
    "GE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "SP": "EUR",
}


@dataclass(frozen=True)
class EconomicEvent:
    uid: str
    summary: str
    description: str
    url: str
    currency: str
    impact: str
    dt_utc: datetime
    dt_local: datetime

    def alert_id(self, lead_minutes: int) -> str:
        return f"{self.uid}|{self.dt_utc.isoformat()}|{lead_minutes}"


def fetch_calendar_ics(timeout_seconds: int) -> bytes:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/135.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(
        FOREX_FACTORY_ICS_URL,
        headers=headers,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.content


def _normalize_description(raw_value: str) -> str:
    return (
        raw_value.replace("\\n", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .strip()
    )


def _extract_impact(summary: str, description: str, categories: str) -> str:
    if "high" in categories.lower():
        return "High"
    match = IMPACT_RE.search(description)
    if match:
        return match.group(1).title()
    stripped = summary.lstrip()
    if stripped.startswith("⁂"):
        return "High"
    if stripped.startswith("⁑"):
        return "Medium"
    if stripped.startswith("⁎"):
        return "Low"
    return "Unknown"


def _extract_currency(summary: str) -> str:
    cleaned = (
        summary.replace("⁂", " ")
        .replace("⁑", " ")
        .replace("⁎", " ")
        .replace("*", " ")
        .upper()
    )
    for token in cleaned.split():
        if token in KNOWN_CURRENCIES:
            return token
        if token in COUNTRY_TO_CURRENCY:
            return COUNTRY_TO_CURRENCY[token]
    return "N/A"


def _to_utc_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
    raise TypeError(f"Unsupported calendar value: {type(value)!r}")


def parse_high_impact_events(ics_data: bytes, target_timezone: ZoneInfo) -> list[EconomicEvent]:
    calendar = Calendar.from_ical(ics_data)
    events: list[EconomicEvent] = []

    for component in calendar.walk():
        if component.name != "VEVENT":
            continue

        dtstart = component.get("DTSTART")
        if dtstart is None:
            continue

        summary = str(component.get("SUMMARY", "Event")).strip()
        description = _normalize_description(str(component.get("DESCRIPTION", "")))
        categories = str(component.get("CATEGORIES", ""))
        impact = _extract_impact(summary, description, categories)
        if impact != "High":
            continue

        dt_utc = _to_utc_datetime(dtstart.dt)
        uid = str(component.get("UID", f"{summary}|{dt_utc.isoformat()}")).strip()
        url = str(component.get("URL", "")).strip()

        events.append(
            EconomicEvent(
                uid=uid,
                summary=summary,
                description=description,
                url=url,
                currency=_extract_currency(summary),
                impact=impact,
                dt_utc=dt_utc,
                dt_local=dt_utc.astimezone(target_timezone),
            )
        )

    return sorted(events, key=lambda event: event.dt_utc)
