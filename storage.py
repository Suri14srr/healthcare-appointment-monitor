from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from models import AppointmentSlot


class NotifiedSlotStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"notified_slots": {}})

    def has_notified(self, slot: AppointmentSlot) -> bool:
        data = self._read()
        notified_slots = data.get("notified_slots", {})
        return slot.notification_key in notified_slots

    def mark_notified(self, slot: AppointmentSlot, notified_at: datetime) -> None:
        data = self._read()
        notified_slots = data.setdefault("notified_slots", {})
        notified_slots[slot.notification_key] = {
            "doctor_name": slot.doctor_name,
            "date": slot.date.isoformat(),
            "day": slot.day_name,
            "time": slot.time_label,
            "slot_id": slot.slot_id,
            "booking_url": slot.booking_url,
            "notified_at": notified_at.isoformat(),
        }
        self._write(data)

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"notified_slots": {}}
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Could not decode notified slot store: {self.path}") from exc

    def _write(self, data: dict[str, Any]) -> None:
        with NamedTemporaryFile(
            "w",
            delete=False,
            encoding="utf-8",
            dir=self.path.parent,
            suffix=".tmp",
        ) as temp_file:
            json.dump(data, temp_file, indent=2, sort_keys=True)
            temp_file.write("\n")
            temp_path = Path(temp_file.name)
        temp_path.replace(self.path)
