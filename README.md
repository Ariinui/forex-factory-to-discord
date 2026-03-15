# Forex Factory to Discord

Systeme Python pour :

- telecharger le calendrier Forex Factory en format ICS
- filtrer uniquement les news `High`
- convertir les heures dans `Pacific/Tahiti`
- envoyer un resume hebdomadaire sur Discord
- envoyer une alerte environ 30 minutes avant chaque news

Le projet est pret pour deux usages :

- execution locale avec Python
- execution cloud avec GitHub Actions

## Structure

```text
Forex factory to Discord/
|-- .github/workflows/
|   |-- alert_check.yml
|   `-- weekly_summary.yml
|-- data/state.json
|-- src/
|   |-- check_alerts.py
|   |-- config.py
|   |-- discord_webhook.py
|   |-- forex_factory.py
|   |-- storage.py
|   `-- weekly_summary.py
|-- .env.example
|-- requirements.txt
`-- README.md
```

## Important corrections from the text specification

- The live Forex Factory feed currently responds on `https://nfs.faireconomy.media/ff_calendar_thisweek.ics`
- `GitHub Actions` scheduled workflows are not available every minute; the practical scheduler here is every 5 minutes
- The Monday summary cron in Tahiti time is `0 18 * * 1` in UTC, not Sunday
- The parser maps Forex Factory country codes to currencies correctly, including `CH -> CNY` and `SZ -> CHF`

## Local setup

1. Open a terminal in this folder.
2. Create a virtual environment if you want:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Configure the webhook:

   Option A:
   create `Discord WEBHOOK.txt` on your Desktop with the webhook URL inside.

   Option B:
   set `DISCORD_WEBHOOK_URL` as an environment variable.

5. Test without sending anything:

   ```powershell
   python -m src.weekly_summary --dry-run
   python -m src.check_alerts --dry-run
   ```

6. Run the real commands:

   ```powershell
   python -m src.weekly_summary
   python -m src.check_alerts
   ```

## Environment variables

You can keep the defaults, but these variables are supported:

```text
DISCORD_WEBHOOK_URL
APP_TIMEZONE=Pacific/Tahiti
ALERT_LEAD_MINUTES=30
ALERT_WINDOW_MINUTES=7
CALENDAR_REFRESH_HOURS=12
DISCORD_ALERT_MENTION=@everyone
```

`ALERT_WINDOW_MINUTES=7` is intentional for GitHub Actions because the scheduler runs every 5 minutes and can start with some delay.

## GitHub Actions setup

1. Create a GitHub repository and push this folder.
2. In GitHub, go to `Settings -> Secrets and variables -> Actions`.
3. Create a repository secret named `DISCORD_WEBHOOK_URL`.
4. Make sure Actions has permission to write repository contents:

   `Settings -> Actions -> General -> Workflow permissions -> Read and write permissions`

5. Enable Actions if needed.
6. Use `workflow_dispatch` once to test both workflows manually.

## How state persistence works

`data/state.json` stores:

- the latest fetched weekly calendar
- sent alert IDs to avoid duplicates
- the time of the latest summary

The workflows commit this file back to the repository only when it changes. That keeps alerts idempotent across GitHub Actions runs.

## Notes

- `weekly_summary.yml` sends the weekly summary every Monday at 08:00 Tahiti time.
- `alert_check.yml` checks every 5 minutes and sends an alert if an event falls in the T-23 to T-31 minute window.
- `check_alerts.py` can refresh the weekly feed itself if the cache is missing or stale.
