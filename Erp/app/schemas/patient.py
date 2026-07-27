from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import (Department, DocumentType, PhysioExercise,
                              PhysioModality, PhysioTraction, Sex)
from app.schemas.staff import Phone


class PatientBase(BaseModel):
    full_name: Annotated[str, StringConstraints(min_length=2, max_length=120)]
    sex: Sex
    date_of_birth: date
    blood_group: str = ""
    phone: Phone
    email: str = ""
    address: str = ""
    emergency_contact_name: str = ""
    emergency_contact_phone: Annotated[str, StringConstraints(pattern=r"^(\d{10})?$")] = ""
    allergies: str = ""
    medical_history: str = ""


class PatientCreate(PatientBase):
    create_login: bool = False
    username: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_.]{3,30}$")] | None = None
    password: Annotated[str, StringConstraints(min_length=8, max_length=72)] | None = None


class PatientUpdate(BaseModel):
    full_name: str | None = None
    blood_group: str | None = None
    phone: Phone | None = None
    email: str | None = None
    address: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    allergies: str | None = None
    medical_history: str | None = None


class PatientOut(PatientBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_code: str
    age: int
    created_at: datetime
    has_login: bool = False


class PatientLite(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_code: str
    full_name: str
    sex: Sex
    phone: str
    age: int


# ------------------------------------------------------------- consultations
class PrescriptionItemIn(BaseModel):
    medicine_id: int | None = None
    medicine_name: Annotated[str, StringConstraints(max_length=120)] = ""
    dosage: str = ""
    frequency: str = ""
    duration_days: Annotated[int, Field(ge=0, le=365)] = 0
    quantity: Annotated[int, Field(ge=0, le=1000)] = 0
    instructions: str = ""


class ConsultationCreate(BaseModel):
    patient_id: int
    department: Department
    chief_complaint: Annotated[str, StringConstraints(min_length=2)]
    diagnosis: str = ""
    clinical_notes: str = ""
    treatments_given: str = ""
    fee: Annotated[int, Field(ge=0)] | None = None      # default: doctor's fee
    follow_up_on: date | None = None
    appointment_id: int | None = None
    prescription_notes: str = ""
    prescription_items: list[PrescriptionItemIn] = []


class PrescriptionItemOut(PrescriptionItemIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class PrescriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    consultation_id: int
    created_at: datetime
    notes: str
    dispensed: bool
    dispensed_at: datetime | None
    items: list[PrescriptionItemOut]


class ConsultationOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_code: str
    doctor_id: int
    doctor_name: str
    department: Department
    visited_at: datetime
    chief_complaint: str
    diagnosis: str
    clinical_notes: str
    treatments_given: str
    fee: int
    follow_up_on: date | None
    prescription: PrescriptionOut | None = None
    bill_id: int | None = None


# ----------------------------------------------------------------- documents
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    doc_type: DocumentType
    title: str
    original_name: str
    content_type: str
    size_bytes: int
    taken_on: date | None
    notes: str
    uploaded_at: datetime


# --------------------------------------------------------------------- physio
class PhysioPlanCreate(BaseModel):
    patient_id: int
    days_count: Annotated[int, Field(ge=1, le=90)]
    exercises: list[PhysioExercise] = []
    modalities: list[PhysioModality] = []
    traction: list[PhysioTraction] = []
    notes: str = ""


class PhysioSessionCreate(BaseModel):
    plan_id: int
    session_date: date
    timing: Annotated[str, StringConstraints(min_length=2, max_length=30)]
    amount: Annotated[int, Field(ge=0, le=100000)]
    notes: str = ""


class PhysioSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    plan_id: int
    session_date: date
    timing: str
    amount: int
    notes: str
    performed_by_name: str = ""


class PhysioPlanOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    prescribed_by_name: str
    prescribed_on: date
    days_count: int
    exercises: list[str]
    modalities: list[str]
    traction: list[str]
    notes: str
    is_active: bool
    sessions_done: int
    sessions: list[PhysioSessionOut] = []
