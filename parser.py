from __future__ import annotations

import json
import re
from datetime import date, time
from typing import Any, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import AppointmentSlot


class AppointmentParseError(RuntimeError):
    pass


CAPTCHA_MARKERS = (
    "captcha",
    "cf-challenge",
    "cloudflare challenge",
    "are you human",
    "verify you are human",
    "bot detection",
)


def detect_anti_bot(html: str) -> bool:
    normalized = html.lower()
    return any(marker in normalized for marker in CAPTCHA_MARKERS)


def parse_slots_from_html(
    html: str,
    doctor_name: str,
    booking_base_url: str,
    doctor_slug: str = "",
) -> list[AppointmentSlot]:
    if detect_anti_bot(html):
        raise AppointmentParseError("Anti-bot or CAPTCHA challenge detected.")

    react_flight_text = _extract_react_flight_text(html)
    if not react_flight_text:
        react_flight_text = BeautifulSoup(html, "html.parser").get_text("\n")

    doctor = _extract_doctor_object(react_flight_text, doctor_name, doctor_slug)
    return _slots_from_doctor_object(doctor, booking_base_url)


def _extract_react_flight_text(html: str) -> str:
    chunks: list[str] = []
    pattern = re.compile(r"self\.__next_f\.push\(\[1,\"((?:\\.|[^\"\\])*)\"\]\)")
    for match in pattern.finditer(html):
        encoded_chunk = match.group(1)
        try:
            chunks.append(json.loads(f'"{encoded_chunk}"'))
        except json.JSONDecodeError:
            continue
    return "".join(chunks)


def _extract_doctor_object(
    text: str,
    doctor_name: str,
    doctor_slug: str = "",
) -> dict[str, Any]:
    doctors = list(_extract_doctor_objects(text))
    normalized_slug = doctor_slug.strip().lower()
    if normalized_slug:
        for doctor in doctors:
            candidate_slug = str(doctor.get("doctor_slug", "")).strip().lower()
            if candidate_slug == normalized_slug:
                return doctor

    for doctor in doctors:
        if _doctor_name_matches(doctor_name, str(doctor.get("name", ""))):
            return doctor

    raise AppointmentParseError(
        f"Doctor not found in page payload: {doctor_name}"
    )


def _extract_doctor_objects(text: str) -> Iterable[dict[str, Any]]:
    seen_starts: set[int] = set()
    for match in re.finditer(r'"doctor_slug"\s*:', text):
        for start in _brace_positions_before(text, match.start()):
            if start in seen_starts:
                continue
            raw_object = _balanced_json_object(text, start)
            if raw_object is None:
                continue
            try:
                parsed = json.loads(raw_object)
            except json.JSONDecodeError:
                continue
            if _looks_like_doctor(parsed):
                seen_starts.add(start)
                yield parsed
                break


def _looks_like_doctor(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("doctor_slug"), str)
        and isinstance(value.get("name"), str)
        and isinstance(value.get("slots"), list)
    )


def _doctor_name_matches(requested_name: str, candidate_name: str) -> bool:
    requested = _normalize_name(requested_name)
    candidate = _normalize_name(candidate_name)
    if requested == candidate:
        return True

    requested_tokens = _name_tokens(requested_name)
    candidate_tokens = _name_tokens(candidate_name)
    if not requested_tokens or not candidate_tokens:
        return False

    candidate_token_set = set(candidate_tokens)
    for token in requested_tokens:
        if token in candidate_token_set:
            continue
        if len(token) == 1 and any(item.startswith(token) for item in candidate_tokens):
            continue
        return False
    return True


def _normalize_name(value: str) -> str:
    return " ".join(_name_tokens(value))


def _name_tokens(value: str) -> list[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return [
        token
        for token in normalized.split()
        if token not in {"dr", "doctor"}
    ]


def _brace_positions_before(text: str, index: int) -> Iterable[int]:
    cursor = index
    while cursor >= 0:
        cursor = text.rfind("{", 0, cursor)
        if cursor >= 0:
            yield cursor


def _balanced_json_object(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


def _slots_from_doctor_object(
    doctor: dict[str, Any],
    booking_base_url: str,
) -> list[AppointmentSlot]:
    doctor_name = str(doctor.get("name", ""))
    doctor_slug = str(doctor.get("doctor_slug", ""))
    if not doctor_name or not doctor_slug:
        raise AppointmentParseError("Doctor payload is missing name or doctor_slug.")

    booking_url = _build_booking_url(booking_base_url, doctor_slug)
    slots: list[AppointmentSlot] = []
    for slot_data in doctor.get("slots", []):
        if not isinstance(slot_data, dict):
            continue
        status = str(slot_data.get("status", "")).upper()
        if status != "AVAILABLE" or slot_data.get("user_facing") is False:
            continue

        try:
            slot_date = date.fromisoformat(str(slot_data["date"]))
            start_time = time.fromisoformat(str(slot_data["start_time"]))
            end_time_raw = slot_data.get("end_time")
            end_time = time.fromisoformat(str(end_time_raw)) if end_time_raw else None
        except (KeyError, TypeError, ValueError) as exc:
            raise AppointmentParseError(f"Invalid slot payload: {slot_data}") from exc

        slot_id = str(slot_data.get("slot_id") or f"{slot_date}-{start_time}")
        slots.append(
            AppointmentSlot(
                doctor_name=doctor_name,
                doctor_slug=doctor_slug,
                slot_id=slot_id,
                date=slot_date,
                start_time=start_time,
                end_time=end_time,
                status=status,
                booking_url=booking_url,
            )
        )

    return slots


def _build_booking_url(booking_base_url: str, doctor_slug: str) -> str:
    normalized_url = booking_base_url.rstrip("/")
    if normalized_url.endswith("/doctors"):
        return f"{normalized_url}/{doctor_slug}"
    return urljoin(normalized_url + "/", f"doctors/{doctor_slug}")
