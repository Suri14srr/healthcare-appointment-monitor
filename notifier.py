from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import structlog

from models import AppointmentSlot


IST = ZoneInfo("Asia/Kolkata")
LOGGER = structlog.get_logger(__name__)


class TelegramNotifier:
    def __init__(
        self,
        bot_token: str | None,
        chat_id: str | None,
        dry_run: bool = False,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds

    def send_slot_alert(self, slot: AppointmentSlot, detected_at: datetime) -> None:
        message = self._build_message(slot, detected_at)
        if self.dry_run:
            LOGGER.info("telegram_dry_run", slot_key=slot.notification_key, message=message)
            return

        if not self.bot_token or not self.chat_id:
            raise RuntimeError("Telegram credentials are not configured.")

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        response = httpx.post(
            url,
            json={
                "chat_id": self.chat_id,
                "text": message,
                "disable_web_page_preview": False,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        LOGGER.info("telegram_notification_sent", slot_key=slot.notification_key)

    @staticmethod
    def _build_message(slot: AppointmentSlot, detected_at: datetime) -> str:
        detected_at_ist = detected_at.astimezone(IST)
        date_label = slot.date.strftime("%A, %d %B %Y")
        timestamp = detected_at_ist.strftime("%Y-%m-%d %H:%M IST")
        return (
            "🚨 Appointment Slot Available\n\n"
            f"Doctor:\n{slot.doctor_name}\n\n"
            f"Date:\n{date_label}\n\n"
            f"Time:\n{slot.time_label}\n\n"
            f"Book Now: {slot.booking_url}\n\n"
            f"Detected At:\n{timestamp}"
        )
