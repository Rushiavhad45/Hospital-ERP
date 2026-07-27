"""OPD slot generation.

Slots are derived from each doctor's shift on the Staff record, at
:data:`~app.core.constants.SLOT_MINUTES` intervals. Sundays are closed.
Bookings are restricted to **today or tomorrow** (hospital policy).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.core.constants import SLOT_MINUTES, SUNDAY
from app.exceptions import BusinessRuleError


def parse_hhmm(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


def validate_booking_date(d: date) -> None:
    today = date.today()
    if d not in (today, today + timedelta(days=1)):
        raise BusinessRuleError(
            "Appointments can be booked for today or tomorrow only.",
            details={"allowed": [str(today), str(today + timedelta(days=1))]},
        )
    if d.weekday() == SUNDAY:
        raise BusinessRuleError("The hospital is closed on Sundays.")


def generate_slots(shift_start: str, shift_end: str, on: date) -> list[str]:
    """All slot start times ("HH:MM") for a shift; past slots removed for today."""
    if on.weekday() == SUNDAY:
        return []
    start = datetime.combine(on, parse_hhmm(shift_start))
    end = datetime.combine(on, parse_hhmm(shift_end))
    now = datetime.now()
    slots: list[str] = []
    cur = start
    while cur + timedelta(minutes=SLOT_MINUTES) <= end:
        if on != date.today() or cur > now:
            slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=SLOT_MINUTES)
    return slots
