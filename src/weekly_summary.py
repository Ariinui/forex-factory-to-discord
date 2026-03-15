from __future__ import annotations

import argparse
from datetime import datetime, timezone

from .config import load_settings
from .discord_webhook import send_weekly_summary
from .forex_factory import fetch_calendar_ics, parse_high_impact_events
from .storage import load_state, replace_events, save_state


def main() -> None:
    parser = argparse.ArgumentParser(description="Send the weekly Forex Factory summary to Discord.")
    parser.add_argument("--dry-run", action="store_true", help="Build payloads without posting to Discord.")
    args = parser.parse_args()

    settings = load_settings(dry_run=args.dry_run)
    old_state = load_state()

    ics_data = fetch_calendar_ics(settings.request_timeout_seconds)
    events = parse_high_impact_events(ics_data, settings.timezone)

    state = replace_events(
        old_state,
        events,
        timezone_name=settings.timezone_name,
        lead_minutes=settings.alert_lead_minutes,
    )
    save_state(state)

    generated_at = state.generated_at or datetime.now(timezone.utc)
    send_weekly_summary(settings, events, generated_at=generated_at)

    if not settings.dry_run:
        state.last_summary_sent_at = datetime.now(timezone.utc)
        save_state(state)

    print(
        f"Weekly summary ready. events={len(events)} "
        f"timezone={settings.timezone_name} dry_run={settings.dry_run}"
    )


if __name__ == "__main__":
    main()
