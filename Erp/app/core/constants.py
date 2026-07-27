"""Hospital identity, tariffs and scheduling constants.

All amounts are integer rupees (₹). Keeping money in integers avoids any
floating point drift in billing.
"""
from __future__ import annotations

HOSPITAL = {
    "name": "Dr. Palaskar Hospital",
    "tagline": "A strong step & a clear sight",
    "departments": ["Orthopaedics", "Ophthalmology", "Physiotherapy"],
    "registration_no": "VVCMC/C-H-202/2014",
    "appointments_phone": ["9545081608", "8087381866"],
    "telephone": ["0250-2380099", "0250-2380888"],
    "email": "palaskarhospital@gmail.com",
    "closed_on": "Sunday",
    "address": "Vasai-Virar, Maharashtra",
}

# ---------------------------------------------------------------------------
# Tariffs (₹)
# ---------------------------------------------------------------------------
CONSULTATION_FEES = {  # by doctor username
    "sameer": 600,
    "lalan": 500,
}
DEFAULT_CONSULTATION_FEE = 500

DOCTOR_VISIT_CHARGE = 400          # per inpatient ward visit
NURSING_CHARGE_PER_DAY = 500
ADMISSION_CHARGE = 1000            # one-time registration/admission fee
EMERGENCY_CHARGE = 1500            # extra for casualty / emergency admissions

ROOM_RATES = {                     # per started 24h day
    "ECONOMY": 1500,
    "DELUXE": 3000,
    "VIP": 6000,
    "ICU": 5000,
}

OT_BASE_CHARGES = {
    "MAJOR": 15000,
    "MINOR": 6000,
}

PHYSIO_SESSION_CHARGE = 350        # default per-session amount (editable per session)

# ---------------------------------------------------------------------------
# Doctor OPD schedules (also used for public appointment slots)
# ---------------------------------------------------------------------------
SLOT_MINUTES = 30

DOCTOR_SCHEDULES = {
    # username: (start "HH:MM", end "HH:MM")
    "sameer": ("11:00", "21:00"),
    "lalan": ("11:00", "18:00"),
}

PHYSIO_HOURS = [("11:00", "13:00"), ("17:00", "21:00")]  # Mon–Sat

SUNDAY = 6  # datetime.weekday() == 6
