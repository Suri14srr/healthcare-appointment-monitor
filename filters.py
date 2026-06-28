from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Iterable

from models import AppointmentSlot


DAY_ALIASES = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

DAY_GROUPS = {
    "all": frozenset(range(7)),
    "any": frozenset(range(7)),
    "weekday": frozenset({0, 1, 2, 3, 4}),
    "weekdays": frozenset({0, 1, 2, 3, 4}),
    "weekend": frozenset({5, 6}),
    "weekends": frozenset({5, 6}),
}


@dataclass(frozen=True, slots=True)
class SlotFilter:
    allowed_weekdays: frozenset[int]
    allowed_dates: frozenset[date]
    start_time: time | None
    end_time: time | None

    @classmethod
    def from_env_values(
        cls,
        slot_days: str,
        slot_dates: str = "",
        slot_start_time: str = "",
        slot_end_time: str = "",
    ) -> "SlotFilter":
        return cls(
            allowed_weekdays=parse_allowed_weekdays(slot_days),
            allowed_dates=parse_allowed_dates(slot_dates),
            start_time=parse_optional_time(slot_start_time, "SLOT_START_TIME"),
            end_time=parse_optional_time(slot_end_time, "SLOT_END_TIME"),
        )

    def matches(self, slot: AppointmentSlot) -> bool:
        if self.allowed_dates and slot.date not in self.allowed_dates:
            return False
        if not self.allowed_dates and slot.date.weekday() not in self.allowed_weekdays:
            return False
        if self.start_time and slot.start_time < self.start_time:
            return False
        if self.end_time and slot.start_time > self.end_time:
            return False
        return True

    @property
    def description(self) -> str:
        day_names = ", ".join(day_name(day) for day in sorted(self.allowed_weekdays))
        parts = [f"days={day_names}"]
        if self.allowed_dates:
            dates = ", ".join(item.isoformat() for item in sorted(self.allowed_dates))
            parts.append(f"dates={dates}")
        if self.start_time:
            parts.append(f"start_time>={self.start_time.isoformat(timespec='minutes')}")
        if self.end_time:
            parts.append(f"start_time<={self.end_time.isoformat(timespec='minutes')}")
        return "; ".join(parts)

def filter_slots(
    slots: Iterable[AppointmentSlot],
    slot_filter: SlotFilter,
) -> list[AppointmentSlot]:
    return [slot for slot in slots if slot_filter.matches(slot)]


def parse_allowed_weekdays(value: str) -> frozenset[int]:
    normalized = value.strip().lower()
    if not normalized:
        return DAY_GROUPS["weekend"]

    days: set[int] = set()
    for token in _split_csv(normalized):
        if token in DAY_GROUPS:
            days.update(DAY_GROUPS[token])
            continue
        if token in DAY_ALIASES:
            days.add(DAY_ALIASES[token])
            continue
        raise ValueError(
            "SLOT_DAYS must be all, weekdays, weekends, or comma-separated day names."
        )

    if not days:
        raise ValueError("SLOT_DAYS did not include any valid days.")
    return frozenset(days)


def parse_allowed_dates(value: str) -> frozenset[date]:
    dates: set[date] = set()
    for token in _split_csv(value):
        try:
            dates.add(date.fromisoformat(token))
        except ValueError as exc:
            raise ValueError(
                "SLOT_DATES must use YYYY-MM-DD values separated by commas."
            ) from exc
    return frozenset(dates)


def parse_optional_time(value: str, env_name: str) -> time | None:
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return time.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{env_name} must use HH:MM or HH:MM:SS format.") from exc


def day_name(day: int) -> str:
    return (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    )[day]


def _split_csv(value: str) -> list[str]:
    return [token.strip().lower() for token in value.split(",") if token.strip()]
