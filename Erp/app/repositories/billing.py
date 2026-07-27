from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models import (Appointment, Bill, BillItem, Consultation, Medicine,
                        Mediclaim, Patient, PrescriptionItem, Reminder, Staff)
from app.models.enums import (AppointmentStatus, BillStatus, ReminderStatus)
from app.repositories.base import BaseRepository


class BillRepository(BaseRepository[Bill]):
    model = Bill

    def _base(self):
        return (select(Bill).options(selectinload(Bill.items),
                                     selectinload(Bill.patient)))

    async def get_full(self, id_: int) -> Bill | None:
        return (await self.db.execute(
            self._base().where(Bill.id == id_))).scalar_one_or_none()

    async def list_bills(self, patient_id: int | None = None,
                         status: BillStatus | None = None,
                         limit: int = 200) -> Sequence[Bill]:
        stmt = self._base().order_by(Bill.generated_at.desc()).limit(limit)
        if patient_id:
            stmt = stmt.where(Bill.patient_id == patient_id)
        if status:
            stmt = stmt.where(Bill.status == status)
        return (await self.db.execute(stmt)).scalars().all()

    async def for_consultation(self, consultation_id: int) -> Bill | None:
        return (await self.db.execute(
            self._base().where(Bill.consultation_id == consultation_id)
        )).scalar_one_or_none()

    async def for_admission(self, admission_id: int) -> Bill | None:
        return (await self.db.execute(
            self._base().where(Bill.admission_id == admission_id)
        )).scalar_one_or_none()

    async def revenue_on(self, day: date) -> int:
        start = datetime.combine(day, datetime.min.time())
        return (await self.db.execute(
            select(func.coalesce(func.sum(Bill.total), 0))
            .where(Bill.status == BillStatus.PAID,
                   Bill.paid_at >= start,
                   Bill.paid_at < start + timedelta(days=1)))).scalar_one()

    async def revenue_series(self, days: int) -> Sequence[tuple[str, int]]:
        start = datetime.combine(date.today() - timedelta(days=days - 1),
                                 datetime.min.time())
        return (await self.db.execute(
            select(func.strftime("%Y-%m-%d", Bill.paid_at),
                   func.coalesce(func.sum(Bill.total), 0))
            .where(Bill.status == BillStatus.PAID, Bill.paid_at >= start)
            .group_by(func.strftime("%Y-%m-%d", Bill.paid_at)))).all()

    async def pending_total(self) -> int:
        return (await self.db.execute(
            select(func.coalesce(func.sum(Bill.total), 0))
            .where(Bill.status == BillStatus.PENDING))).scalar_one()


class AppointmentRepository(BaseRepository[Appointment]):
    model = Appointment

    def _base(self):
        return (select(Appointment).options(selectinload(Appointment.patient),
                                            selectinload(Appointment.doctor)))

    async def get_full(self, id_: int) -> Appointment | None:
        return (await self.db.execute(
            self._base().where(Appointment.id == id_))).scalar_one_or_none()

    async def slot_taken(self, doctor_id: int, day: date, slot: str) -> bool:
        return (await self.db.execute(
            select(func.count()).select_from(Appointment)
            .where(Appointment.doctor_id == doctor_id,
                   Appointment.appointment_date == day,
                   Appointment.slot == slot,
                   Appointment.status.in_([AppointmentStatus.BOOKED,
                                           AppointmentStatus.CONFIRMED]))
        )).scalar_one() > 0

    async def inactive_for_slot(self, doctor_id: int, day: date,
                                slot: str) -> Appointment | None:
        """A CANCELLED / NO_SHOW / COMPLETED row holding this slot's unique
        key, if any — reused by the service when the slot is rebooked."""
        return (await self.db.execute(
            select(Appointment)
            .where(Appointment.doctor_id == doctor_id,
                   Appointment.appointment_date == day,
                   Appointment.slot == slot,
                   Appointment.status.not_in([AppointmentStatus.BOOKED,
                                              AppointmentStatus.CONFIRMED]))
            .limit(1)
        )).scalar_one_or_none()

    async def booked_slots(self, doctor_id: int, day: date) -> list[str]:
        return list((await self.db.execute(
            select(Appointment.slot)
            .where(Appointment.doctor_id == doctor_id,
                   Appointment.appointment_date == day,
                   Appointment.status.in_([AppointmentStatus.BOOKED,
                                           AppointmentStatus.CONFIRMED]))
        )).scalars().all())

    async def list_between(self, start: date, end: date,
                           patient_id: int | None = None) -> Sequence[Appointment]:
        stmt = (self._base()
                .where(Appointment.appointment_date >= start,
                       Appointment.appointment_date <= end)
                .order_by(Appointment.appointment_date, Appointment.slot))
        if patient_id:
            stmt = stmt.where(Appointment.patient_id == patient_id)
        return (await self.db.execute(stmt)).scalars().all()

    async def for_patient(self, patient_id: int, limit: int = 50) -> Sequence[Appointment]:
        return (await self.db.execute(
            self._base().where(Appointment.patient_id == patient_id)
            .order_by(Appointment.appointment_date.desc(), Appointment.slot.desc())
            .limit(limit))).scalars().all()

    async def by_code_phone(self, code: str, phone: str) -> Appointment | None:
        return (await self.db.execute(
            self._base().where(Appointment.code == code.upper())
        )).scalar_one_or_none()


class ReminderRepository(BaseRepository[Reminder]):
    model = Reminder

    async def list_reminders(self, status: ReminderStatus | None = None,
                             limit: int = 100) -> Sequence[tuple[Reminder, str | None]]:
        stmt = (select(Reminder, Patient.full_name)
                .outerjoin(Patient, Reminder.patient_id == Patient.id)
                .order_by(Reminder.due_at).limit(limit))
        if status:
            stmt = stmt.where(Reminder.status == status)
        return (await self.db.execute(stmt)).all()


class MediclaimRepository(BaseRepository[Mediclaim]):
    model = Mediclaim

    async def for_admission(self, admission_id: int) -> Mediclaim | None:
        return (await self.db.execute(
            select(Mediclaim).where(Mediclaim.admission_id == admission_id)
        )).scalar_one_or_none()

    async def list_claims(self, patient_id: int | None = None
                          ) -> Sequence[tuple[Mediclaim, str, str]]:
        stmt = (select(Mediclaim, Patient.full_name, Patient.patient_code)
                .join(Patient, Mediclaim.patient_id == Patient.id)
                .order_by(Mediclaim.created_at.desc()))
        if patient_id:
            stmt = stmt.where(Mediclaim.patient_id == patient_id)
        return (await self.db.execute(stmt)).all()


class AnalyticsRepository:
    """Cross-domain aggregates for the dashboards."""

    def __init__(self, db):
        self.db = db

    async def consultations_series(self, days: int) -> Sequence[tuple[str, int]]:
        start = datetime.combine(date.today() - timedelta(days=days - 1),
                                 datetime.min.time())
        return (await self.db.execute(
            select(func.strftime("%Y-%m-%d", Consultation.visited_at), func.count())
            .where(Consultation.visited_at >= start)
            .group_by(func.strftime("%Y-%m-%d", Consultation.visited_at)))).all()

    async def department_split(self, days: int = 90) -> Sequence[tuple[str, int]]:
        start = datetime.now() - timedelta(days=days)
        return (await self.db.execute(
            select(Consultation.department, func.count())
            .where(Consultation.visited_at >= start)
            .group_by(Consultation.department))).all()

    async def top_medicines(self, limit: int = 6) -> Sequence[tuple[str, int]]:
        return (await self.db.execute(
            select(Medicine.name, func.sum(PrescriptionItem.quantity).label("q"))
            .join(Medicine, PrescriptionItem.medicine_id == Medicine.id)
            .group_by(Medicine.name).order_by(func.sum(PrescriptionItem.quantity).desc())
            .limit(limit))).all()

    async def new_patients_on(self, day: date) -> int:
        start = datetime.combine(day, datetime.min.time())
        return (await self.db.execute(
            select(func.count()).select_from(Patient)
            .where(Patient.created_at >= start,
                   Patient.created_at < start + timedelta(days=1)))).scalar_one()
