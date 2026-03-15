from __future__ import annotations

import argparse
from datetime import datetime, timezone

from .config import load_settings
from .discord_webhook import send_alert
from .forex_factory import fetch_calendar_ics, parse_high_impact_events
from .storage import load_state, needs_calendar_refresh, replace_events, save_state


def _refresh_state_if_needed(settings, state):
    now_utc = datetime.now(timezone.utc)
    if not needs_calendar_refresh(
        state,
        now_utc=now_utc,
        refresh_after_hours=settings.calendar_refresh_hours,
    ):
        return state, False

    ics_data = fetch_calendar_ics(settings.request_timeout_seconds)
    events = parse_high_impact_events(ics_data, settings.timezone)
    updated_state = replace_events(
        state,
        events,
        timezone_name=settings.timezone_name,
        lead_minutes=settings.alert_lead_minutes,
    )
    save_state(updated_state)
    return updated_state, True


def main() -> None:
    parser = argparse.ArgumentParser(description="Check for upcoming high-impact alerts.")
    parser.add_argument("--dry-run", action="store_true", help="Build payloads without posting to Discord.")
    args = parser.parse_args()

    settings = load_settings(dry_run=args.dry_run)
    state = load_state()
    state, refreshed = _refresh_state_if_needed(settings, state)

    now_utc = datetime.now(timezone.utc)
    lower_bound = settings.alert_lead_minutes - settings.alert_window_minutes
    upper_bound = settings.alert_lead_minutes + 1

    alerts_sent = 0
    for event in state.events:
        minutes_until = (event.dt_utc - now_utc).total_seconds() / 60
        alert_id = event.alert_id(settings.alert_lead_minutes)
        if alert_id in state.sent_alerts:
            continue
        if lower_bound <= minutes_until <= upper_bound:
            send_alert(settings, event)
            state.sent_alerts.add(alert_id)
            alerts_sent += 1

    if alerts_sent or refreshed:
        save_state(state)

    print(
        f"Alert check complete. sent={alerts_sent} refreshed={refreshed} "
        f"events={len(state.events)} dry_run={settings.dry_run}"
    )


if __name__ == "__main__":
    main()
