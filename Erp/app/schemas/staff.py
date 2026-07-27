from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import (AttendanceStatus, Designation, PayrollMode, Role,
                              Sex)

Phone = Annotated[str, StringConstraints(pattern=r"^\d{10}$")]
Aadhar = Annotated[str, StringConstraints(pattern=r"^(\d{12})?$")]
Pan = Annotated[str, StringConstraints(pattern=r"^([A-Z]{5}\d{4}[A-Z])?$")]
Ifsc = Annotated[str, StringConstraints(pattern=r"^([A-Z]{4}0[A-Z0-9]{6})?$")]
HHMM = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]


# --------------------------------------------------------------------- auth
class LoginIn(BaseModel):
    username: Annotated[str, StringConstraints(min_length=2, max_length=50)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=72)]


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: Annotated[str, StringConstraints(min_length=8, max_length=72)]


class MeOut(BaseModel):
    id: int
    username: str
    role: Role
    full_name: str
    staff_id: int | None = None
    patient_id: int | None = None
    designation: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: MeOut


# -------------------------------------------------------------------- staff
class StaffBase(BaseModel):
    full_name: Annotated[str, StringConstraints(min_length=2, max_length=120)]
    sex: Sex
    date_of_birth: date
    designation: Designation
    qualification: str = ""
    department: str = "GENERAL"
    phone: Phone
    email: str = ""
    address: str = ""
    aadhar_number: Aadhar = ""
    pan_number: Pan = ""
    bank_account_number: Annotated[str, StringConstraints(pattern=r"^(\d{6,20})?$")] = ""
    bank_ifsc: Ifsc = ""
    bank_name: str = ""
    monthly_salary: Annotated[int, Field(ge=0, le=10_000_000)]
    date_joined: date
    shift_start: HHMM = "10:00"
    shift_end: HHMM = "18:00"


class StaffCreate(StaffBase):
    username: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_.]{3,30}$")]
    password: Annotated[str, StringConstraints(min_length=8, max_length=72)]


class StaffUpdate(BaseModel):
    full_name: str | None = None
    qualification: str | None = None
    department: str | None = None
    phone: Phone | None = None
    email: str | None = None
    address: str | None = None
    aadhar_number: Aadhar | None = None
    pan_number: Pan | None = None
    bank_account_number: str | None = None
    bank_ifsc: Ifsc | None = None
    bank_name: str | None = None
    monthly_salary: int | None = Field(default=None, ge=0)
    shift_start: HHMM | None = None
    shift_end: HHMM | None = None
    is_active: bool | None = None


class StaffOut(StaffBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    age: int
    is_active: bool
    username: str | None = None
    # sensitive fields are nulled for non-admin viewers
    aadhar_number: str | None = None      # type: ignore[assignment]
    pan_number: str | None = None         # type: ignore[assignment]
    bank_account_number: str | None = None  # type: ignore[assignment]
    bank_ifsc: str | None = None          # type: ignore[assignment]
    bank_name: str | None = None
    monthly_salary: int | None = None     # type: ignore[assignment]


class StaffLite(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    designation: Designation
    department: str


# ---------------------------------------------------------------- attendance
class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    staff_id: int
    day: date
    check_in: datetime | None
    check_out: datetime | None
    hours_worked: float
    status: AttendanceStatus
    note: str


class AttendanceMarkIn(BaseModel):
    staff_id: int
    day: date
    status: AttendanceStatus
    note: str = ""


class HeatmapCell(BaseModel):
    day: date
    hours: float
    status: str


# ------------------------------------------------------------------ payroll
class PayrollPayIn(BaseModel):
    staff_id: int
    month: Annotated[int, Field(ge=1, le=12)]
    year: Annotated[int, Field(ge=2014, le=2100)]
    mode: PayrollMode = PayrollMode.MANUAL
    amount_override: Annotated[int, Field(ge=0)] | None = None


class AutopayIn(BaseModel):
    month: Annotated[int, Field(ge=1, le=12)]
    year: Annotated[int, Field(ge=2014, le=2100)]


class SalaryPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    staff_id: int
    month: int
    year: int
    amount: int
    mode: PayrollMode
    reference: str
    paid_on: datetime
