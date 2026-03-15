from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import FOREX_FACTORY_ICS_URL, STATE_FILE
from .forex_factory import EconomicEvent


@dataclass
class State:
    generated_at: datetime | None = None
    last_summary_sent_at: datetime | None = None
    source_url: str = FOREX_FACTORY_ICS_URL
    timezone: str = "Pacific/Tahiti"
    events: list[EconomicEvent] = field(default_factory=list)
    sent_alerts: set[str] = field(default_factory=set)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _serialize_event(event: EconomicEvent) -> dict[str, str]:
    return {
        "uid": event.uid,
        "summary": event.summary,
        "description": event.description,
        "url": event.url,
        "currency": event.currency,
        "impact": event.impact,
        "dt_utc": event.dt_utc.isoformat(),
        "dt_local": event.dt_local.isoformat(),
    }


def _deserialize_event(payload: dict[str, str]) -> EconomicEvent:
    return EconomicEvent(
        uid=payload["uid"],
        summary=payload["summary"],
        description=payload.get("description", ""),
        url=payload.get("url", ""),
        currency=payload.get("currency", "N/A"),
        impact=payload.get("impact", "Unknown"),
        dt_utc=datetime.fromisoformat(payload["dt_utc"]),
        dt_local=datetime.fromisoformat(payload["dt_local"]),
    )


def load_state(path: Path = STATE_FILE) -> State:
    if not path.exists():
        return State()

    payload = json.loads(path.read_text(encoding="utf-8"))
    events = [_deserialize_event(event) for event in payload.get("events", [])]
    return State(
        generated_at=_parse_datetime(payload.get("generated_at")),
        last_summary_sent_at=_parse_datetime(payload.get("last_summary_sent_at")),
        source_url=payload.get("source_url", FOREX_FACTORY_ICS_URL),
        timezone=payload.get("timezone", "Pacific/Tahiti"),
        events=events,
        sent_alerts=set(payload.get("sent_alerts", [])),
    )


def save_state(state: State, path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": state.generated_at.isoformat() if state.generated_at else None,
        "last_summary_sent_at": (
            state.last_summary_sent_at.isoformat() if state.last_summary_sent_at else None
        ),
        "source_url": state.source_url,
        "timezone": state.timezone,
        "events": [_serialize_event(event) for event in state.events],
        "sent_alerts": sorted(state.sent_alerts),
    }
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(path)


def prune_sent_alerts(
    sent_alerts: set[str],
    events: list[EconomicEvent],
    lead_minutes: int,
) -> set[str]:
    valid_ids = {event.alert_id(lead_minutes) for event in events}
    return {alert_id for alert_id in sent_alerts if alert_id in valid_ids}


def replace_events(
    state: State,
    events: list[EconomicEvent],
    timezone_name: str,
    lead_minutes: int,
) -> State:
    return State(
        generated_at=datetime.now(timezone.utc),
        last_summary_sent_at=state.last_summary_sent_at,
        source_url=FOREX_FACTORY_ICS_URL,
        timezone=timezone_name,
        events=events,
        sent_alerts=prune_sent_alerts(state.sent_alerts, events, lead_minutes),
    )


def needs_calendar_refresh(
    state: State,
    *,
    now_utc: datetime,
    refresh_after_hours: int,
) -> bool:
    if state.generated_at is None or not state.events:
        return True

    if now_utc - state.generated_at > timedelta(hours=refresh_after_hours):
        return True

    latest_event = max(event.dt_utc for event in state.events)
    return latest_event < now_utc
