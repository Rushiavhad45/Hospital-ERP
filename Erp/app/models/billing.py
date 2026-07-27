from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (AppointmentStatus, BillItemCategory, BillStatus,
                              BillType, BookedVia, ClaimStatus, Department,
                              PaymentMode, ReminderCategory, ReminderStatus)
from app.models.user import _enum


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(primary_key=True)
    bill_number: Mapped[str] = mapped_column(sa.String(20), unique=True, index=True)
    bill_type: Mapped[BillType] = mapped_column(_enum(BillType), index=True)
    patient_id: Mapped[int] = mapped_column(sa.ForeignKey("patients.id"), index=True)
    consultation_id: Mapped[int | None] = mapped_column(sa.ForeignKey("consultations.id"))
    admission_id: Mapped[int | None] = mapped_column(sa.ForeignKey("admissions.id"))
    surgery_id: Mapped[int | None] = mapped_column(sa.ForeignKey("surgeries.id"))

    subtotal: Mapped[int] = mapped_column(default=0)   # ₹
    discount: Mapped[int] = mapped_column(default=0)
    total: Mapped[int] = mapped_column(default=0)
    status: Mapped[BillStatus] = mapped_column(
        _enum(BillStatus), default=BillStatus.PENDING, index=True)
    payment_mode: Mapped[PaymentMode | None] = mapped_column(_enum(PaymentMode))
    transaction_ref: Mapped[str] = mapped_column(sa.String(40), default="")
    generated_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)
    paid_at: Mapped[datetime | None]
    notes: Mapped[str] = mapped_column(sa.String(300), default="")

    patient = relationship("Patient")
    items: Mapped[list["BillItem"]] = relationship(
        back_populates="bill", cascade="all, delete-orphan")


class BillItem(Base):
    __tablename__ = "bill_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    bill_id: Mapped[int] = mapped_column(sa.ForeignKey("bills.id"), index=True)
    category: Mapped[BillItemCategory] = mapped_column(_enum(BillItemCategory))
    description: Mapped[str] = mapped_column(sa.String(220))
    quantity: Mapped[int] = mapped_column(default=1)
    unit_price: Mapped[int] = mapped_column(default=0)   # ₹
    amount: Mapped[int] = mapped_column(default=0)       # quantity × unit_price

    bill: Mapped[Bill] = relationship(back_populates="items")


class Appointment(Base):
    """OPD appointment — bookable only for **today or tomorrow**. Guests (not
    yet registered patients) may book from the public site; a staff member
    confirms the appointment when the patient arrives ~30 min early."""

    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(sa.String(12), unique=True, index=True)
    patient_id: Mapped[int | None] = mapped_column(sa.ForeignKey("patients.id"), index=True)
    guest_name: Mapped[str] = mapped_column(sa.String(120), default="")
    guest_phone: Mapped[str] = mapped_column(sa.String(15), default="", index=True)

    doctor_id: Mapped[int] = mapped_column(sa.ForeignKey("staff.id"), index=True)
    department: Mapped[Department] = mapped_column(_enum(Department))
    appointment_date: Mapped[date] = mapped_column(index=True)
    slot: Mapped[str] = mapped_column(sa.String(5))            # "HH:MM"
    reason: Mapped[str] = mapped_column(sa.String(300), default="")

    status: Mapped[AppointmentStatus] = mapped_column(
        _enum(AppointmentStatus), default=AppointmentStatus.BOOKED, index=True)
    booked_via: Mapped[BookedVia] = mapped_column(_enum(BookedVia))
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    confirmed_at: Mapped[datetime | None]
    confirmed_by_user_id: Mapped[int | None] = mapped_column(sa.ForeignKey("users.id"))

    __table_args__ = (
        # Only ACTIVE bookings claim a slot — cancelled / no-show rows must
        # not block rebooking (they are reused by the service regardless).
        sa.Index("uq_doctor_slot_active", "doctor_id", "appointment_date",
                 "slot", unique=True,
                 sqlite_where=sa.text(
                     "status IN ('BOOKED','CONFIRMED')")),
    )

    patient = relationship("Patient")
    doctor = relationship("Staff")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(sa.String(160))
    message: Mapped[str] = mapped_column(sa.Text, default="")
    category: Mapped[ReminderCategory] = mapped_column(
        _enum(ReminderCategory), index=True)
    patient_id: Mapped[int | None] = mapped_column(sa.ForeignKey("patients.id"))
    admission_id: Mapped[int | None] = mapped_column(sa.ForeignKey("admissions.id"))
    due_at: Mapped[datetime] = mapped_column(index=True)
    status: Mapped[ReminderStatus] = mapped_column(
        _enum(ReminderStatus), default=ReminderStatus.PENDING, index=True)
    created_by_user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    done_at: Mapped[datetime | None]

    patient = relationship("Patient")


class Mediclaim(Base):
    """Insurance claim file — auto-opened at admission, auto-finalized with a
    frozen summary (diagnosis, stay, itemised bill) at discharge."""

    __tablename__ = "mediclaims"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_number: Mapped[str] = mapped_column(sa.String(16), unique=True, index=True)
    admission_id: Mapped[int] = mapped_column(sa.ForeignKey("admissions.id"), unique=True)
    patient_id: Mapped[int] = mapped_column(sa.ForeignKey("patients.id"), index=True)
    insurer_name: Mapped[str] = mapped_column(sa.String(120), default="")
    policy_number: Mapped[str] = mapped_column(sa.String(60), default="")
    tpa_name: Mapped[str] = mapped_column(sa.String(120), default="")
    status: Mapped[ClaimStatus] = mapped_column(
        _enum(ClaimStatus), default=ClaimStatus.DRAFT, index=True)
    summary_json: Mapped[str] = mapped_column(sa.Text, default="{}")  # frozen at discharge
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    finalized_at: Mapped[datetime | None]

    patient = relationship("Patient")
    admission = relationship("Admission")
