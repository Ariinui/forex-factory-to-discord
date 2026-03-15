from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Iterable

import requests

from .config import Settings
from .forex_factory import EconomicEvent

def _chunked(items: list[dict], chunk_size: int) -> Iterable[list[dict]]:
    for index in range(0, len(items), chunk_size):
        yield items[index : index + chunk_size]


def _clean_description(description: str) -> str:
    lines: list[str] = []
    for raw_line in description.replace("\\n", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith("impact:"):
            continue
        if line.lower().startswith("view event:"):
            continue
        lines.append(line)
    return "\n".join(lines[:6])[:900]


def _post_payload(settings: Settings, payload: dict) -> None:
    if settings.dry_run:
        embeds = payload.get("embeds", [])
        print(f"[dry-run] Discord payload prepared with {len(embeds)} embed(s).")
        return

    response = requests.post(
        settings.webhook_url,
        json=payload,
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()


def _currency_label(currency: str) -> str:
    return currency


def send_weekly_summary(
    settings: Settings,
    events: list[EconomicEvent],
    *,
    generated_at: datetime,
) -> None:
    if not events:
        _post_payload(
            settings,
            {
                "content": (
                    "Forex Factory weekly summary\n\n"
                    "No high-impact events found for the current week."
                ),
                "embeds": [],
            },
        )
        return

    grouped: dict[date, list[EconomicEvent]] = defaultdict(list)
    for event in events:
        grouped[event.dt_local.date()].append(event)

    first_day = min(grouped)
    last_day = max(grouped)
    currency_counts: dict[str, int] = {}
    for event in events:
        currency_counts[event.currency] = currency_counts.get(event.currency, 0) + 1

    currency_bar = " | ".join(
        f"{_currency_label(currency)} x{count}"
        for currency, count in sorted(currency_counts.items(), key=lambda item: (-item[1], item[0]))
    )[:1024]

    embeds: list[dict] = [
        {
            "title": "Forex Factory weekly summary",
            "description": (
                f"{len(events)} high-impact event(s)\n"
                f"Timezone: {settings.timezone_name}\n"
                f"Window: {first_day.isoformat()} -> {last_day.isoformat()}"
            ),
            "color": 0xD35400,
            "fields": [
                {
                    "name": "Currencies",
                    "value": currency_bar or "N/A",
                    "inline": False,
                }
            ],
            "timestamp": generated_at.isoformat().replace("+00:00", "Z"),
        }
    ]

    for event_date in sorted(grouped):
        lines = []
        for event in sorted(grouped[event_date], key=lambda item: item.dt_utc):
            title = event.summary.lstrip("⁂⁑⁎* ").strip()
            line = (
                f"`{event.dt_local.strftime('%H:%M')}` "
                f"{_currency_label(event.currency)} - {title}"
            )
            if event.url:
                line += f" [link]({event.url})"
            lines.append(line)

        embeds.append(
            {
                "title": event_date.strftime("%A %d %B %Y"),
                "description": "\n".join(lines)[:3800],
                "color": 0x1F8B4C,
                "footer": {
                    "text": f"{len(grouped[event_date])} high-impact event(s) in {settings.timezone_name}"
                },
            }
        )

    for index, chunk in enumerate(_chunked(embeds, 10), start=1):
        _post_payload(
            settings,
            {
                "content": "Weekly Forex Factory summary" if index == 1 else "",
                "embeds": chunk,
            },
        )


def send_alert(settings: Settings, event: EconomicEvent) -> None:
    title = event.summary.lstrip("⁂⁑⁎* ").strip()
    details = _clean_description(event.description)

    fields = [
        {
            "name": "Time",
            "value": event.dt_local.strftime("%Y-%m-%d %H:%M"),
            "inline": True,
        },
        {
            "name": "Timezone",
            "value": settings.timezone_name,
            "inline": True,
        },
        {
            "name": "Currency",
            "value": _currency_label(event.currency),
            "inline": True,
        },
    ]
    if details:
        fields.append(
            {
                "name": "Details",
                "value": details[:1024],
                "inline": False,
            }
        )

    content = settings.mention_text.strip()
    embed = {
        "title": "Forex Factory alert",
        "description": title,
        "color": 0xE74C3C,
        "fields": fields,
        "timestamp": event.dt_utc.isoformat().replace("+00:00", "Z"),
        "footer": {
            "text": f"Scheduled alert from Forex Factory ({event.impact})"
        },
    }
    if event.url:
        embed["url"] = event.url

    payload = {
        "content": f"{content} High-impact news in about {settings.alert_lead_minutes} minutes".strip(),
        "embeds": [embed],
    }
    _post_payload(settings, payload)
