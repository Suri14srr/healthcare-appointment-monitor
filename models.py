from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True, slots=True)
class AppointmentSlot:
    doctor_name: str
    doctor_slug: str
    slot_id: str
    date: date
    start_time: time
    end_time: time | None
    status: str
    booking_url: str

    @property
    def notification_key(self) -> str:
        return f"{self.doctor_slug}:{self.slot_id}:{self.date.isoformat()}:{self.start_time.isoformat()}"

    @property
    def day_name(self) -> str:
        return self.date.strftime("%A")

    @property
    def time_label(self) -> str:
        return self.start_time.strftime("%I:%M %p").lstrip("0")


@dataclass(frozen=True, slots=True)
class MonitorResult:
    slots_found: int
    matching_slots_found: int
    notifications_sent: int
    response_time_ms: int
    source: str
