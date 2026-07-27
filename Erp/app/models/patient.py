from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import Department, DocumentType, Sex
from app.models.user import _enum


class Patient(Base):
    """Patient master record. ``user_id`` is nullable — walk-in patients may
    never receive portal credentials."""

    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_code: Mapped[str] = mapped_column(sa.String(12), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(sa.ForeignKey("users.id"), unique=True)

    full_name: Mapped[str] = mapped_column(sa.String(120), index=True)
    sex: Mapped[Sex] = mapped_column(_enum(Sex))
    date_of_birth: Mapped[date]
    blood_group: Mapped[str] = mapped_column(sa.String(5), default="")
    phone: Mapped[str] = mapped_column(sa.String(15), index=True)
    email: Mapped[str] = mapped_column(sa.String(120), default="")
    address: Mapped[str] = mapped_column(sa.Text, default="")
    emergency_contact_name: Mapped[str] = mapped_column(sa.String(120), default="")
    emergency_contact_phone: Mapped[str] = mapped_column(sa.String(15), default="")
    allergies: Mapped[str] = mapped_column(sa.Text, default="")
    medical_history: Mapped[str] = mapped_column(sa.Text, default="")

    created_by_user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    user = relationship("User", back_populates="patient", foreign_keys=[user_id])
    consultations: Mapped[list["Consultation"]] = relationship(back_populates="patient")
    documents: Mapped[list["PatientDocument"]] = relationship(back_populates="patient")

    @property
    def age(self) -> int:
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


class Consultation(Base):
    """One OPD visit / consulting record, written by the doctor while consulting."""

    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(sa.ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(sa.ForeignKey("staff.id"), index=True)
    appointment_id: Mapped[int | None] = mapped_column(sa.ForeignKey("appointments.id"))

    department: Mapped[Department] = mapped_column(_enum(Department))
    visited_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)
    chief_complaint: Mapped[str] = mapped_column(sa.Text)          # reason / regarding
    diagnosis: Mapped[str] = mapped_column(sa.Text, default="")
    clinical_notes: Mapped[str] = mapped_column(sa.Text, default="")
    treatments_given: Mapped[str] = mapped_column(sa.Text, default="")  # from catalogue
    fee: Mapped[int] = mapped_column(default=0)  # ₹
    follow_up_on: Mapped[date | None]

    patient: Mapped[Patient] = relationship(back_populates="consultations")
    doctor = relationship("Staff")
    prescription: Mapped["Prescription | None"] = relationship(
        back_populates="consultation", uselist=False)


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    consultation_id: Mapped[int] = mapped_column(
        sa.ForeignKey("consultations.id"), unique=True)
    patient_id: Mapped[int] = mapped_column(sa.ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(sa.ForeignKey("staff.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    notes: Mapped[str] = mapped_column(sa.Text, default="")
    dispensed: Mapped[bool] = mapped_column(default=False)
    dispensed_at: Mapped[datetime | None]

    consultation: Mapped[Consultation] = relationship(back_populates="prescription")
    items: Mapped[list["PrescriptionItem"]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan")


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    prescription_id: Mapped[int] = mapped_column(
        sa.ForeignKey("prescriptions.id"), index=True)
    medicine_id: Mapped[int | None] = mapped_column(sa.ForeignKey("medicines.id"))
    medicine_name: Mapped[str] = mapped_column(sa.String(120))  # snapshot / free text
    dosage: Mapped[str] = mapped_column(sa.String(60), default="")       # 1-0-1
    frequency: Mapped[str] = mapped_column(sa.String(60), default="")    # after meals
    duration_days: Mapped[int] = mapped_column(default=0)
    quantity: Mapped[int] = mapped_column(default=0)  # units to dispense
    instructions: Mapped[str] = mapped_column(sa.String(200), default="")

    prescription: Mapped[Prescription] = relationship(back_populates="items")
    medicine = relationship("Medicine")


class PatientDocument(Base):
    """Scans, reports and papers attached to the patient record."""

    __tablename__ = "patient_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(sa.ForeignKey("patients.id"), index=True)
    doc_type: Mapped[DocumentType] = mapped_column(_enum(DocumentType))
    title: Mapped[str] = mapped_column(sa.String(160))
    file_path: Mapped[str] = mapped_column(sa.String(260))   # relative to UPLOAD_DIR
    original_name: Mapped[str] = mapped_column(sa.String(160))
    content_type: Mapped[str] = mapped_column(sa.String(80))
    size_bytes: Mapped[int] = mapped_column(default=0)
    taken_on: Mapped[date | None]
    notes: Mapped[str] = mapped_column(sa.String(300), default="")
    uploaded_by_user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(default=datetime.now)

    patient: Mapped[Patient] = relationship(back_populates="documents")


class PhysioPlan(Base):
    """Doctor's physiotherapy prescription: N days + exercises/modalities/traction."""

    __tablename__ = "physio_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(sa.ForeignKey("patients.id"), index=True)
    prescribed_by_id: Mapped[int] = mapped_column(sa.ForeignKey("staff.id"))
    prescribed_on: Mapped[date] = mapped_column(default=date.today)
    days_count: Mapped[int]
    exercises: Mapped[str] = mapped_column(sa.Text, default="")   # "; " joined values
    modalities: Mapped[str] = mapped_column(sa.Text, default="")
    traction: Mapped[str] = mapped_column(sa.Text, default="")
    notes: Mapped[str] = mapped_column(sa.Text, default="")
    is_active: Mapped[bool] = mapped_column(default=True)

    patient = relationship("Patient")
    prescribed_by = relationship("Staff")
    sessions: Mapped[list["PhysioSession"]] = relationship(back_populates="plan")


class PhysioSession(Base):
    """Each attended session: date, timing and amount are recorded."""

    __tablename__ = "physio_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(sa.ForeignKey("physio_plans.id"), index=True)
    session_date: Mapped[date] = mapped_column(index=True)
    timing: Mapped[str] = mapped_column(sa.String(30))     # e.g. "5:30 PM – 6:10 PM"
    amount: Mapped[int]                                    # ₹ charged for the session
    performed_by_id: Mapped[int] = mapped_column(sa.ForeignKey("staff.id"))
    notes: Mapped[str] = mapped_column(sa.String(300), default="")

    plan: Mapped[PhysioPlan] = relationship(back_populates="sessions")
    performed_by = relationship("Staff")
