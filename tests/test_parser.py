from __future__ import annotations

from filters import SlotFilter, filter_slots
from parser import parse_slots_from_html


DOCTOR_NAME = "Dr Akanksha Prasad Cherala"
APPOINTMENT_URL = "https://www.superhealth.co.in/appointment/koramangala/doctors"


def _html_with_payload(
    slots_json: str,
    doctor_name: str = DOCTOR_NAME,
    doctor_slug: str = "dr-akanksha-prasad-cherala-dermatologist",
) -> str:
    payload = (
        '0:{"doctor_id":"b4112525-9ebc-4e1a-afb4-e1208b73f714",'
        f'"doctor_slug":"{doctor_slug}",'
        f'"name":"{doctor_name}",'
        '"specialization":"Dermatology",'
        f'"slots":{slots_json}'
        "}"
    )
    escaped = payload.encode("unicode_escape").decode("ascii").replace('"', '\\"')
    return f'<html><script>self.__next_f.push([1,"{escaped}"])</script></html>'


def test_parse_available_slots_from_react_flight_payload() -> None:
    html = _html_with_payload(
        "["
        '{"slot_id":"sat-1030","date":"2026-07-18","start_time":"10:30:00",'
        '"end_time":"10:45:00","status":"AVAILABLE","user_facing":true},'
        '{"slot_id":"hidden","date":"2026-07-18","start_time":"11:00:00",'
        '"end_time":"11:15:00","status":"AVAILABLE","user_facing":false},'
        '{"slot_id":"booked","date":"2026-07-18","start_time":"12:00:00",'
        '"end_time":"12:15:00","status":"BOOKED","user_facing":true}'
        "]"
    )

    slots = parse_slots_from_html(html, DOCTOR_NAME, APPOINTMENT_URL)

    assert len(slots) == 1
    assert slots[0].doctor_name == DOCTOR_NAME
    assert slots[0].day_name == "Saturday"
    assert slots[0].time_label == "10:30 AM"
    assert slots[0].booking_url.endswith(
        "/appointment/koramangala/doctors/dr-akanksha-prasad-cherala-dermatologist"
    )


def test_parse_doctor_by_short_name_with_initial() -> None:
    html = _html_with_payload(
        "["
        '{"slot_id":"akhil-mon","date":"2026-06-29","start_time":"15:00:00",'
        '"end_time":"15:15:00","status":"AVAILABLE","user_facing":true}'
        "]",
        doctor_name="Dr Akhil Krishnanand Bhat",
        doctor_slug="dr-akhil-krishnanand-bhat-general-surgeon",
    )

    slots = parse_slots_from_html(html, "Dr. Akhil K. Bhat", APPOINTMENT_URL)

    assert len(slots) == 1
    assert slots[0].doctor_name == "Dr Akhil Krishnanand Bhat"


def test_parse_doctor_by_slug_when_name_is_short() -> None:
    html = _html_with_payload(
        "["
        '{"slot_id":"akhil-mon","date":"2026-06-29","start_time":"15:00:00",'
        '"end_time":"15:15:00","status":"AVAILABLE","user_facing":true}'
        "]",
        doctor_name="Dr Akhil Krishnanand Bhat",
        doctor_slug="dr-akhil-krishnanand-bhat-general-surgeon",
    )

    slots = parse_slots_from_html(
        html,
        "Dr. Something Else",
        APPOINTMENT_URL,
        doctor_slug="dr-akhil-krishnanand-bhat-general-surgeon",
    )

    assert len(slots) == 1
    assert slots[0].doctor_name == "Dr Akhil Krishnanand Bhat"


def test_slot_filter_can_keep_only_weekends() -> None:
    html = _html_with_payload(
        "["
        '{"slot_id":"fri","date":"2026-07-17","start_time":"10:30:00",'
        '"end_time":"10:45:00","status":"AVAILABLE","user_facing":true},'
        '{"slot_id":"sat","date":"2026-07-18","start_time":"10:30:00",'
        '"end_time":"10:45:00","status":"AVAILABLE","user_facing":true},'
        '{"slot_id":"sun","date":"2026-07-19","start_time":"10:30:00",'
        '"end_time":"10:45:00","status":"AVAILABLE","user_facing":true},'
        '{"slot_id":"mon","date":"2026-07-20","start_time":"10:30:00",'
        '"end_time":"10:45:00","status":"AVAILABLE","user_facing":true}'
        "]"
    )
    slots = parse_slots_from_html(html, DOCTOR_NAME, APPOINTMENT_URL)

    weekend_slots = filter_slots(
        slots,
        SlotFilter.from_env_values(slot_days="weekends"),
    )

    assert [slot.slot_id for slot in weekend_slots] == ["sat", "sun"]


def test_slot_filter_supports_weekdays_specific_dates_and_times() -> None:
    html = _html_with_payload(
        "["
        '{"slot_id":"mon-early","date":"2026-07-20","start_time":"09:30:00",'
        '"end_time":"09:45:00","status":"AVAILABLE","user_facing":true},'
        '{"slot_id":"mon-ok","date":"2026-07-20","start_time":"10:30:00",'
        '"end_time":"10:45:00","status":"AVAILABLE","user_facing":true},'
        '{"slot_id":"tue-other-date","date":"2026-07-21","start_time":"10:30:00",'
        '"end_time":"10:45:00","status":"AVAILABLE","user_facing":true},'
        '{"slot_id":"sat-weekend","date":"2026-07-18","start_time":"10:30:00",'
        '"end_time":"10:45:00","status":"AVAILABLE","user_facing":true}'
        "]"
    )
    slots = parse_slots_from_html(html, DOCTOR_NAME, APPOINTMENT_URL)

    matching_slots = filter_slots(
        slots,
        SlotFilter.from_env_values(
            slot_days="weekdays",
            slot_dates="2026-07-20",
            slot_start_time="10:00",
            slot_end_time="11:00",
        ),
    )

    assert [slot.slot_id for slot in matching_slots] == ["mon-ok"]


def test_slot_dates_take_priority_over_slot_days() -> None:
    html = _html_with_payload(
        "["
        '{"slot_id":"sat","date":"2026-07-18","start_time":"10:30:00",'
        '"end_time":"10:45:00","status":"AVAILABLE","user_facing":true},'
        '{"slot_id":"mon","date":"2026-07-20","start_time":"10:30:00",'
        '"end_time":"10:45:00","status":"AVAILABLE","user_facing":true}'
        "]"
    )
    slots = parse_slots_from_html(html, DOCTOR_NAME, APPOINTMENT_URL)

    matching_slots = filter_slots(
        slots,
        SlotFilter.from_env_values(
            slot_days="weekends",
            slot_dates="2026-07-20",
        ),
    )

    assert [slot.slot_id for slot in matching_slots] == ["mon"]
