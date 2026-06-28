# Superhealth Appointment Monitor

Production-ready Python monitor for appointment slots for a configurable doctor on Superhealth Koramangala.

The monitor fetches the Superhealth doctors page, parses the embedded Next.js appointment payload, filters slots using `.env` rules, sends Telegram alerts, and records notified slots locally to prevent duplicates.

## Installation

Use Python 3.12.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

On Linux/macOS:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Configuration

Copy `.env.example` to `.env` and fill in:

```env
TELEGRAM_BOT_TOKEN=123456:your-bot-token
TELEGRAM_CHAT_ID=123456789
```

Create a Telegram bot with BotFather, start a chat with the bot, and use your chat ID as `TELEGRAM_CHAT_ID`. For a group, add the bot to the group and use the group chat ID.

Useful settings:

```env
DOCTOR_NAME=Dr Akanksha Prasad Cherala
DOCTOR_SLUG=
SLOT_DAYS=weekends
SLOT_DATES=
SLOT_START_TIME=
SLOT_END_TIME=
RUN_ONCE=false
DRY_RUN=false
CHECK_INTERVAL_SECONDS=300
USE_PLAYWRIGHT_FALLBACK=true
```

Slot filter examples:

```env
# Only Saturday and Sunday, default behavior
SLOT_DAYS=weekends

# Monday to Friday
SLOT_DAYS=weekdays

# Any day
SLOT_DAYS=all

# Specific days
SLOT_DAYS=monday,wednesday,saturday

# Only these dates
# When SLOT_DATES is filled, these exact dates are checked instead of SLOT_DAYS.
SLOT_DATES=2026-07-18,2026-07-19

# Only slots starting between 10:00 AM and 1:30 PM
SLOT_START_TIME=10:00
SLOT_END_TIME=13:30
```

Doctor matching:

```env
# Full display name from Superhealth
DOCTOR_NAME=Dr Akhil Krishnanand Bhat

# Optional stable slug, useful when you prefer a short name in DOCTOR_NAME
DOCTOR_SLUG=dr-akhil-krishnanand-bhat-general-surgeon
```

Set `DRY_RUN=true` to log Telegram messages without sending them.

## Running Locally

Run continuously every 5 minutes:

```bash
python app.py
```

Run one check:

```bash
$env:RUN_ONCE="true"
$env:DRY_RUN="true"
python app.py
```

Logs are written as structured JSON to stdout and `logs/monitor.log`.

## GitHub Actions

The workflow in `.github/workflows/monitor.yml` runs every 5 minutes and also supports manual execution.

Add these repository secrets in GitHub:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

The workflow installs Python 3.12 dependencies, installs Chromium for Playwright fallback, and executes `python app.py` with `RUN_ONCE=true`. After each run it commits `data/notified_slots.json` back to the repository when a new slot notification has been recorded, which preserves duplicate suppression across scheduled GitHub Actions runs.

## Architecture

- `app.py`: application entry point and dependency wiring.
- `config.py`: environment-based configuration.
- `monitor.py`: fetch, retry, parse, filter, notify, and execution logging.
- `filters.py`: configurable day, date, and time-window slot matching.
- `parser.py`: React Flight payload extraction, doctor lookup, slot parsing, anti-bot detection.
- `notifier.py`: Telegram message formatting and delivery.
- `storage.py`: local JSON store for duplicate notification prevention.
- `logging_config.py`: structured JSON logging setup.
- `tests/`: unit tests for parsing and weekend filtering.

## Behavior

The normal path uses HTTP because the Superhealth page currently embeds slot data in the server-rendered Next.js payload. If that fails, Playwright opens the page, waits for JavaScript/lazy loading, and returns the rendered HTML.

Only slots with `status=AVAILABLE` and `user_facing=true` are considered. If `SLOT_DATES` is filled, notifications are sent only for those exact dates. If `SLOT_DATES` is blank, notifications are sent only for dates whose day matches `SLOT_DAYS`. `SLOT_START_TIME` and `SLOT_END_TIME` further limit matching slots by start time.

## Troubleshooting

- Missing Telegram credentials: set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, or set `DRY_RUN=true`.
- Playwright browser missing: run `python -m playwright install chromium`.
- Page structure changed: check `logs/monitor.log` for `parse_failed`; the app exits the run gracefully instead of crashing the loop.
- CAPTCHA or anti-bot challenge: the app logs `anti_bot_detected` and exits that run cleanly.
- Duplicate alerts: inspect `data/notified_slots.json`; each notified slot is keyed by doctor, slot ID, date, and start time.

## Tests

```bash
pytest
```
