from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from filters import SlotFilter


load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    doctor_name: str = os.getenv("DOCTOR_NAME", "Dr Akanksha Prasad Cherala")
    doctor_slug: str = os.getenv("DOCTOR_SLUG", "")
    location_slug: str = os.getenv("LOCATION_SLUG", "koramangala")
    appointment_url: str = os.getenv(
        "APPOINTMENT_URL",
        "https://www.superhealth.co.in/appointment/koramangala/doctors",
    )
    base_url: str = os.getenv("BASE_URL", "https://www.superhealth.co.in")
    check_interval_seconds: int = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    retry_base_seconds: float = float(os.getenv("RETRY_BASE_SECONDS", "1.5"))
    use_playwright_fallback: bool = _get_bool("USE_PLAYWRIGHT_FALLBACK", True)
    headless: bool = _get_bool("PLAYWRIGHT_HEADLESS", True)
    run_once: bool = _get_bool("RUN_ONCE", False)
    telegram_bot_token: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = os.getenv("TELEGRAM_CHAT_ID")
    data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
    logs_dir: Path = Path(os.getenv("LOGS_DIR", "logs"))
    notified_slots_file: Path = Path(
        os.getenv("NOTIFIED_SLOTS_FILE", "data/notified_slots.json")
    )
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    dry_run: bool = _get_bool("DRY_RUN", False)
    slot_filter: SlotFilter = field(
        default_factory=lambda: SlotFilter.from_env_values(
            slot_days=os.getenv("SLOT_DAYS", "weekends"),
            slot_dates=os.getenv("SLOT_DATES", ""),
            slot_start_time=os.getenv("SLOT_START_TIME", ""),
            slot_end_time=os.getenv("SLOT_END_TIME", ""),
        )
    )

    def validate(self) -> None:
        if not self.dry_run and (
            not self.telegram_bot_token or not self.telegram_chat_id
        ):
            raise ValueError(
                "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required unless DRY_RUN=true."
            )
        if (
            self.slot_filter.start_time
            and self.slot_filter.end_time
            and self.slot_filter.start_time > self.slot_filter.end_time
        ):
            raise ValueError("SLOT_START_TIME must be earlier than SLOT_END_TIME.")


def load_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.notified_slots_file.parent.mkdir(parents=True, exist_ok=True)
    return settings
