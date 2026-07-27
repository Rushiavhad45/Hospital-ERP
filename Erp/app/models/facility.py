from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (AdmissionStatus, AdmissionType, CareLogType,
                              OTCategory, OTStatus, RoomStatus, RoomType,
                              SurgeryStatus)
from app.models.user import _enum


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_number: Mapped[str] = mapped_column(sa.String(10), unique=True)
    room_type: Mapped[RoomType] = mapped_column(_enum(RoomType), index=True)
    daily_rate: Mapped[int]                                        # ₹ / started day
    status: Mapped[RoomStatus] = mapped_column(
        _enum(RoomStatus), default=RoomStatus.AVAILABLE, index=True)
    floor: Mapped[int] = mapped_column(default=1)
    notes: Mapped[str] = mapped_column(sa.String(200), default="")

    admissions: Mapped[list["Admission"]] = relationship(back_populates="room")


class Admission(Base):
    """In-patient stay: from admission until discharge (bill auto-generated)."""

    __tablename__ = "admissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(sa.ForeignKey("patients.id"), index=True)
    room_id: Mapped[int] = mapped_column(sa.ForeignKey("rooms.id"), index=True)
    primary_doctor_id: Mapped[int] = mapped_column(sa.ForeignKey("staff.id"))
    assigned_nurse_id: Mapped[int | None] = mapped_column(sa.ForeignKey("staff.id"))

    admission_type: Mapped[AdmissionType] = mapped_column(_enum(AdmissionType))
    reason: Mapped[str] = mapped_column(sa.Text)
    diagnosis: Mapped[str] = mapped_column(sa.Text, default="")
    admitted_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)
    discharged_at: Mapped[datetime | None]
    status: Mapped[AdmissionStatus] = mapped_column(
        _enum(AdmissionStatus), default=AdmissionStatus.ADMITTED, index=True)
    discharge_summary: Mapped[str] = mapped_column(sa.Text, default="")
    created_by_user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"))

    patient = relationship("Patient")
    room: Mapped[Room] = relationship(back_populates="admissions")
    primary_doctor = relationship("Staff", foreign_keys=[primary_doctor_id])
    assigned_nurse = relationship("Staff", foreign_keys=[assigned_nurse_id])
    care_logs: Mapped[list["CareLog"]] = relationship(
        back_populates="admission", cascade="all, delete-orphan")
    surgeries: Mapped[list["Surgery"]] = relationship(back_populates="admission")


class CareLog(Base):
    """Ward timeline: medicines given, doctor visits, meals, vitals, treatments,
    services and clinical notes — each with a timestamp and the staff member."""

    __tablename__ = "care_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    admission_id: Mapped[int] = mapped_column(sa.ForeignKey("admissions.id"), index=True)
    log_type: Mapped[CareLogType] = mapped_column(_enum(CareLogType), index=True)
    description: Mapped[str] = mapped_column(sa.Text)
    medicine_id: Mapped[int | None] = mapped_column(sa.ForeignKey("medicines.id"))
    quantity: Mapped[int] = mapped_column(default=0)
    charge: Mapped[int] = mapped_column(default=0)          # ₹ — flows into the IPD bill
    doctor_id: Mapped[int | None] = mapped_column(sa.ForeignKey("staff.id"))
    logged_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)
    logged_by_user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"))

    admission: Mapped[Admission] = relationship(back_populates="care_logs")
    medicine = relationship("Medicine")
    doctor = relationship("Staff", foreign_keys=[doctor_id])


class OperationTheatre(Base):
    __tablename__ = "operation_theatres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(40), unique=True)
    category: Mapped[OTCategory] = mapped_column(_enum(OTCategory))
    status: Mapped[OTStatus] = mapped_column(_enum(OTStatus), default=OTStatus.AVAILABLE)
    equipment: Mapped[str] = mapped_column(sa.Text, default="")  # fixed installed kit

    surgeries: Mapped[list["Surgery"]] = relationship(back_populates="theatre")


class Surgery(Base):
    """A booked/performed operation. If linked to an admission its charge flows
    into the discharge bill; otherwise a standalone SURGERY bill is raised."""

    __tablename__ = "surgeries"

    id: Mapped[int] = mapped_column(primary_key=True)
    theatre_id: Mapped[int] = mapped_column(sa.ForeignKey("operation_theatres.id"))
    patient_id: Mapped[int] = mapped_column(sa.ForeignKey("patients.id"), index=True)
    admission_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("admissions.id"), index=True)
    surgeon_id: Mapped[int] = mapped_column(sa.ForeignKey("staff.id"))

    name: Mapped[str] = mapped_column(sa.String(160))
    scheduled_at: Mapped[datetime] = mapped_column(index=True)
    started_at: Mapped[datetime | None]
    ended_at: Mapped[datetime | None]
    status: Mapped[SurgeryStatus] = mapped_column(
        _enum(SurgeryStatus), default=SurgeryStatus.SCHEDULED, index=True)
    equipment_used: Mapped[str] = mapped_column(sa.Text, default="")
    charges: Mapped[int] = mapped_column(default=0)  # ₹
    notes: Mapped[str] = mapped_column(sa.Text, default="")

    theatre: Mapped[OperationTheatre] = relationship(back_populates="surgeries")
    admission: Mapped[Admission | None] = relationship(back_populates="surgeries")
    patient = relationship("Patient")
    surgeon = relationship("Staff")
