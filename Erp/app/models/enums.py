"""Domain enums — stored as strings in SQLite for readability."""
from __future__ import annotations

import enum


class StrEnum(str, enum.Enum):
    def __str__(self) -> str:  # pragma: no cover
        return self.value


class Role(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    STAFF = "STAFF"
    PATIENT = "PATIENT"


class Sex(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class Designation(StrEnum):
    DOCTOR = "DOCTOR"
    NURSE = "NURSE"
    CLERK = "CLERK"
    PHARMACIST = "PHARMACIST"
    PHYSIOTHERAPIST = "PHYSIOTHERAPIST"
    INTERN = "INTERN"
    TECHNICIAN = "TECHNICIAN"
    HOUSEKEEPING = "HOUSEKEEPING"
    OTHER = "OTHER"


class Department(StrEnum):
    ORTHOPAEDICS = "ORTHOPAEDICS"
    OPHTHALMOLOGY = "OPHTHALMOLOGY"
    PHYSIOTHERAPY = "PHYSIOTHERAPY"
    GENERAL = "GENERAL"


class AttendanceStatus(StrEnum):
    PRESENT = "PRESENT"
    HALF_DAY = "HALF_DAY"
    ABSENT = "ABSENT"
    LEAVE = "LEAVE"
    WEEK_OFF = "WEEK_OFF"


class PayrollStatus(StrEnum):
    PAID = "PAID"


class PayrollMode(StrEnum):
    AUTOPAY = "AUTOPAY"
    MANUAL = "MANUAL"


class RoomType(StrEnum):
    ECONOMY = "ECONOMY"
    DELUXE = "DELUXE"
    VIP = "VIP"
    ICU = "ICU"


class RoomStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    MAINTENANCE = "MAINTENANCE"


class AdmissionType(StrEnum):
    PLANNED = "PLANNED"
    EMERGENCY = "EMERGENCY"   # casualty


class AdmissionStatus(StrEnum):
    ADMITTED = "ADMITTED"
    DISCHARGED = "DISCHARGED"


class CareLogType(StrEnum):
    MEDICATION = "MEDICATION"
    DOCTOR_VISIT = "DOCTOR_VISIT"
    VITALS = "VITALS"
    MEAL = "MEAL"
    TREATMENT = "TREATMENT"
    SERVICE = "SERVICE"
    NOTE = "NOTE"


class OTStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    MAINTENANCE = "MAINTENANCE"


class SurgeryStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class OTCategory(StrEnum):
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class BillType(StrEnum):
    OPD = "OPD"                # consultation + dispensed medicines
    IPD = "IPD"                # inpatient, generated at discharge
    SURGERY = "SURGERY"        # day-care surgery without admission
    PHARMACY = "PHARMACY"


class BillStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class PaymentMode(StrEnum):
    UPI = "UPI"
    CASH = "CASH"
    CARD = "CARD"
    NETBANKING = "NETBANKING"


class BillItemCategory(StrEnum):
    CONSULTATION = "CONSULTATION"
    ROOM = "ROOM"
    NURSING = "NURSING"
    DOCTOR_VISIT = "DOCTOR_VISIT"
    MEDICINE = "MEDICINE"
    OT = "OT"
    TREATMENT = "TREATMENT"
    SERVICE = "SERVICE"
    PHYSIOTHERAPY = "PHYSIOTHERAPY"
    ADMISSION = "ADMISSION"
    EMERGENCY = "EMERGENCY"
    OTHER = "OTHER"


class AppointmentStatus(StrEnum):
    BOOKED = "BOOKED"
    CONFIRMED = "CONFIRMED"      # patient arrived, marked by staff
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class BookedVia(StrEnum):
    PORTAL = "PORTAL"
    GUEST = "GUEST"
    WALK_IN = "WALK_IN"


class ReminderCategory(StrEnum):
    ADMISSION = "ADMISSION"
    DISCHARGE = "DISCHARGE"
    EMERGENCY = "EMERGENCY"
    FOLLOW_UP = "FOLLOW_UP"
    GENERAL = "GENERAL"


class ReminderStatus(StrEnum):
    PENDING = "PENDING"
    DONE = "DONE"


class ClaimStatus(StrEnum):
    DRAFT = "DRAFT"            # auto-created at admission
    FINALIZED = "FINALIZED"    # auto at discharge, summary frozen
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DocumentType(StrEnum):
    XRAY = "XRAY"
    MRI = "MRI"
    CT_SCAN = "CT_SCAN"
    ULTRASOUND = "ULTRASOUND"
    LAB_REPORT = "LAB_REPORT"
    PRESCRIPTION_PAPER = "PRESCRIPTION_PAPER"
    TREATMENT_PAPER = "TREATMENT_PAPER"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    OTHER = "OTHER"


class StockTxnType(StrEnum):
    IN = "IN"
    OUT = "OUT"
    ADJUSTMENT = "ADJUSTMENT"


# ---------------------------------------------------------------------------
# Physiotherapy catalogue (per hospital record protocol)
# ---------------------------------------------------------------------------
class PhysioExercise(StrEnum):
    CORE_STRENGTHENING = "Core Muscle Strengthening"
    CERVICAL_SPINE_STRENGTHENING = "Cervical Spine Strengthening"
    LS_SPINE_STRENGTHENING = "L.S. Spine Strengthening"
    KNEE_RIGHT = "Knee Joint Strengthening (Right)"
    KNEE_LEFT = "Knee Joint Strengthening (Left)"
    KNEE_BOTH = "Knee Joint Strengthening (Both)"
    SHOULDER_RIGHT = "Shoulder Joint Strengthening (Right)"
    SHOULDER_LEFT = "Shoulder Joint Strengthening (Left)"
    SHOULDER_BOTH = "Shoulder Joint Strengthening (Both)"
    SHOULDER_MOB_RIGHT = "Shoulder Mobilization & Capsular Stretching (Right)"
    SHOULDER_MOB_LEFT = "Shoulder Mobilization & Capsular Stretching (Left)"
    SHOULDER_MOB_BOTH = "Shoulder Mobilization & Capsular Stretching (Both)"


class PhysioModality(StrEnum):
    SWD = "SWD (Short Wave Diathermy)"
    IFT = "IFT (Interferential Therapy)"
    TENS = "TENS (Transcutaneous Electrical Nerve Stimulation)"
    US = "U.S. (Ultrasound Therapy)"


class PhysioTraction(StrEnum):
    LUMBAR = "Lumbar Traction"
    CERVICAL = "Cervical Traction"
