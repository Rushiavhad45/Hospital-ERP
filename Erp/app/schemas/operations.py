from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import (AdmissionStatus, AdmissionType,
                              AppointmentStatus, BillItemCategory, BillStatus,
                              BillType, CareLogType, ClaimStatus, Department,
                              OTCategory, OTStatus, PaymentMode,
                              ReminderCategory, ReminderStatus, RoomStatus,
                              RoomType, StockTxnType, SurgeryStatus)
from app.schemas.staff import HHMM, Phone


# ------------------------------------------------------------------ pharmacy
class MedicineCreate(BaseModel):
    name: Annotated[str, StringConstraints(min_length=2, max_length=120)]
    generic_name: str = ""
    category: str = ""
    manufacturer: str = ""
    unit: str = "tablet"
    unit_price: Annotated[int, Field(ge=0, le=1_000_000)]
    stock_quantity: Annotated[int, Field(ge=0)] = 0
    reorder_level: Annotated[int, Field(ge=0)] = 10
    batch_number: str = ""
    expiry_date: date | None = None


class MedicineUpdate(BaseModel):
    generic_name: str | None = None
    category: str | None = None
    manufacturer: str | None = None
    unit: str | None = None
    unit_price: Annotated[int, Field(ge=0)] | None = None
    reorder_level: Annotated[int, Field(ge=0)] | None = None
    batch_number: str | None = None
    expiry_date: date | None = None
    is_active: bool | None = None


class MedicineOut(MedicineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    low_stock: bool


class StockAdjustIn(BaseModel):
    medicine_id: int
    txn_type: StockTxnType
    quantity: Annotated[int, Field(ge=1, le=100000)]
    reference: str = ""


class StockTxnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    medicine_id: int
    medicine_name: str = ""
    txn_type: StockTxnType
    quantity: int
    balance_after: int
    reference: str
    created_at: datetime


# --------------------------------------------------------------------- rooms
class RoomCreate(BaseModel):
    room_number: Annotated[str, StringConstraints(min_length=1, max_length=10)]
    room_type: RoomType
    daily_rate: Annotated[int, Field(ge=0, le=1_000_000)]
    floor: Annotated[int, Field(ge=0, le=20)] = 1
    notes: str = ""


class RoomUpdate(BaseModel):
    daily_rate: Annotated[int, Field(ge=0)] | None = None
    status: RoomStatus | None = None    # AVAILABLE <-> MAINTENANCE only
    floor: int | None = None
    notes: str | None = None


class RoomOut(RoomCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: RoomStatus
    occupant_name: str | None = None
    occupant_patient_id: int | None = None
    admission_id: int | None = None
    admitted_at: datetime | None = None
    doctor_name: str | None = None
    nurse_name: str | None = None


# ---------------------------------------------------------------- admissions
class AdmissionCreate(BaseModel):
    patient_id: int
    room_id: int
    primary_doctor_id: int
    assigned_nurse_id: int | None = None
    admission_type: AdmissionType
    reason: Annotated[str, StringConstraints(min_length=2)]
    diagnosis: str = ""
    admitted_at: datetime | None = None   # backdating allowed (not future)


class DischargeIn(BaseModel):
    discharge_summary: str = ""
    discount: Annotated[int, Field(ge=0)] = 0


class CareLogCreate(BaseModel):
    admission_id: int
    log_type: CareLogType
    description: Annotated[str, StringConstraints(min_length=1)]
    medicine_id: int | None = None
    quantity: Annotated[int, Field(ge=0, le=1000)] = 0
    charge: Annotated[int, Field(ge=0, le=1_000_000)] = 0
    doctor_id: int | None = None


class CareLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    admission_id: int
    log_type: CareLogType
    description: str
    medicine_name: str | None = None
    quantity: int
    charge: int
    doctor_name: str | None = None
    logged_at: datetime
    logged_by: str = ""


class AdmissionOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_code: str
    room_id: int
    room_number: str
    room_type: RoomType
    primary_doctor_id: int
    doctor_name: str
    nurse_name: str | None
    admission_type: AdmissionType
    reason: str
    diagnosis: str
    admitted_at: datetime
    discharged_at: datetime | None
    status: AdmissionStatus
    discharge_summary: str
    bill_id: int | None = None
    claim_number: str | None = None
    hours_admitted: float | None = None


# ------------------------------------------------------------------------ OT
class TheatreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: OTCategory
    status: OTStatus
    equipment: str


class SurgeryCreate(BaseModel):
    theatre_id: int
    patient_id: int
    admission_id: int | None = None
    surgeon_id: int
    name: Annotated[str, StringConstraints(min_length=2, max_length=160)]
    scheduled_at: datetime
    charges: Annotated[int, Field(ge=0, le=10_000_000)] | None = None
    equipment_used: str = ""
    notes: str = ""


class SurgeryStatusIn(BaseModel):
    status: SurgeryStatus
    equipment_used: str | None = None
    notes: str | None = None
    charges: Annotated[int, Field(ge=0)] | None = None


class SurgeryOut(BaseModel):
    id: int
    theatre_id: int
    theatre_name: str
    patient_id: int
    patient_name: str
    admission_id: int | None
    surgeon_id: int
    surgeon_name: str
    name: str
    scheduled_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    status: SurgeryStatus
    equipment_used: str
    charges: int
    notes: str


# ------------------------------------------------------------------- billing
class BillItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: BillItemCategory
    description: str
    quantity: int
    unit_price: int
    amount: int


class BillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    bill_number: str
    bill_type: BillType
    patient_id: int
    patient_name: str = ""
    patient_code: str = ""
    consultation_id: int | None
    admission_id: int | None
    subtotal: int
    discount: int
    total: int
    status: BillStatus
    payment_mode: PaymentMode | None
    transaction_ref: str
    generated_at: datetime
    paid_at: datetime | None
    notes: str
    items: list[BillItemOut] = []


class PayBillIn(BaseModel):
    mode: PaymentMode
    upi_id: str | None = None   # demo only — never charged


# -------------------------------------------------------------- appointments
class GuestAppointmentIn(BaseModel):
    name: Annotated[str, StringConstraints(min_length=2, max_length=120)]
    phone: Phone
    doctor_id: int
    appointment_date: date
    slot: HHMM
    reason: Annotated[str, StringConstraints(max_length=300)] = ""


class PortalAppointmentIn(BaseModel):
    doctor_id: int
    appointment_date: date
    slot: HHMM
    reason: Annotated[str, StringConstraints(max_length=300)] = ""


class AppointmentStatusIn(BaseModel):
    status: AppointmentStatus


class AppointmentOut(BaseModel):
    id: int
    code: str
    patient_id: int | None
    patient_name: str
    phone: str
    doctor_id: int
    doctor_name: str
    department: Department
    appointment_date: date
    slot: str
    reason: str
    status: AppointmentStatus
    booked_via: str
    created_at: datetime
    confirmed_at: datetime | None


# ----------------------------------------------------------------- reminders
class ReminderCreate(BaseModel):
    title: Annotated[str, StringConstraints(min_length=2, max_length=160)]
    message: str = ""
    category: ReminderCategory = ReminderCategory.GENERAL
    patient_id: int | None = None
    due_at: datetime


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    message: str
    category: ReminderCategory
    patient_id: int | None
    patient_name: str | None = None
    admission_id: int | None
    due_at: datetime
    status: ReminderStatus
    created_at: datetime


# ----------------------------------------------------------------- mediclaim
class MediclaimUpdate(BaseModel):
    insurer_name: str | None = None
    policy_number: str | None = None
    tpa_name: str | None = None
    status: ClaimStatus | None = None


class MediclaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    claim_number: str
    admission_id: int
    patient_id: int
    patient_name: str = ""
    patient_code: str = ""
    insurer_name: str
    policy_number: str
    tpa_name: str
    status: ClaimStatus
    summary: dict = {}
    created_at: datetime
    finalized_at: datetime | None
