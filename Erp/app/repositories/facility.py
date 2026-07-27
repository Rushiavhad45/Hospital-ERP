from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import aliased, selectinload

from app.models import (Admission, CareLog, Medicine, OperationTheatre,
                        Patient, Room, Staff, StockTransaction, Surgery, User)
from app.models.enums import AdmissionStatus, RoomStatus, SurgeryStatus
from app.repositories.base import BaseRepository


class MedicineRepository(BaseRepository[Medicine]):
    model = Medicine

    async def by_name(self, name: str) -> Medicine | None:
        return (await self.db.execute(
            select(Medicine).where(func.lower(Medicine.name) == name.lower())
        )).scalar_one_or_none()

    async def search(self, q: str = "", low_only: bool = False) -> Sequence[Medicine]:
        stmt = select(Medicine).where(Medicine.is_active.is_(True)).order_by(Medicine.name)
        if q:
            stmt = stmt.where(Medicine.name.ilike(f"%{q}%"))
        meds = (await self.db.execute(stmt)).scalars().all()
        if low_only:
            meds = [m for m in meds if m.low_stock]
        return meds

    async def transactions(self, medicine_id: int | None = None,
                           limit: int = 100) -> Sequence[tuple[StockTransaction, str]]:
        stmt = (select(StockTransaction, Medicine.name)
                .join(Medicine, StockTransaction.medicine_id == Medicine.id)
                .order_by(StockTransaction.created_at.desc()).limit(limit))
        if medicine_id:
            stmt = stmt.where(StockTransaction.medicine_id == medicine_id)
        return (await self.db.execute(stmt)).all()


class RoomRepository(BaseRepository[Room]):
    model = Room

    async def by_number(self, number: str) -> Room | None:
        return (await self.db.execute(
            select(Room).where(Room.room_number == number))).scalar_one_or_none()

    async def board(self) -> Sequence[tuple]:
        """Every room + current occupant (if any)."""
        nurse = aliased(Staff)
        return (await self.db.execute(
            select(Room, Admission.id, Admission.admitted_at,
                   Patient.id, Patient.full_name, Staff.full_name, nurse.full_name)
            .outerjoin(Admission, (Admission.room_id == Room.id)
                       & (Admission.status == AdmissionStatus.ADMITTED))
            .outerjoin(Patient, Admission.patient_id == Patient.id)
            .outerjoin(Staff, Admission.primary_doctor_id == Staff.id)
            .outerjoin(nurse, Admission.assigned_nurse_id == nurse.id)
            .order_by(Room.room_type, Room.room_number))).all()

    async def occupancy_by_type(self) -> Sequence[tuple[str, str, int]]:
        return (await self.db.execute(
            select(Room.room_type, Room.status, func.count())
            .group_by(Room.room_type, Room.status))).all()


class AdmissionRepository(BaseRepository[Admission]):
    model = Admission

    def _base(self):
        return (select(Admission)
                .options(selectinload(Admission.patient),
                         selectinload(Admission.room),
                         selectinload(Admission.primary_doctor),
                         selectinload(Admission.assigned_nurse)))

    async def get_full(self, id_: int) -> Admission | None:
        return (await self.db.execute(
            self._base().where(Admission.id == id_))).scalar_one_or_none()

    async def active_for_patient(self, patient_id: int) -> Admission | None:
        return (await self.db.execute(
            select(Admission).where(Admission.patient_id == patient_id,
                                    Admission.status == AdmissionStatus.ADMITTED)
        )).scalar_one_or_none()

    async def list_admissions(self, status: AdmissionStatus | None = None,
                              patient_id: int | None = None,
                              limit: int = 100) -> Sequence[Admission]:
        stmt = self._base().order_by(Admission.admitted_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(Admission.status == status)
        if patient_id:
            stmt = stmt.where(Admission.patient_id == patient_id)
        return (await self.db.execute(stmt)).scalars().all()

    async def admitted_on(self, day: date) -> int:
        start = datetime.combine(day, datetime.min.time())
        return (await self.db.execute(
            select(func.count()).select_from(Admission)
            .where(Admission.admitted_at >= start,
                   Admission.admitted_at < start + timedelta(days=1)))).scalar_one()

    async def discharged_on(self, day: date) -> int:
        start = datetime.combine(day, datetime.min.time())
        return (await self.db.execute(
            select(func.count()).select_from(Admission)
            .where(Admission.discharged_at >= start,
                   Admission.discharged_at < start + timedelta(days=1)))).scalar_one()


class CareLogRepository(BaseRepository[CareLog]):
    model = CareLog

    async def for_admission(self, admission_id: int) -> Sequence[tuple]:
        doctor = aliased(Staff)
        return (await self.db.execute(
            select(CareLog, Medicine.name, doctor.full_name, User.full_name)
            .outerjoin(Medicine, CareLog.medicine_id == Medicine.id)
            .outerjoin(doctor, CareLog.doctor_id == doctor.id)
            .join(User, CareLog.logged_by_user_id == User.id)
            .where(CareLog.admission_id == admission_id)
            .order_by(CareLog.logged_at.desc()))).all()

    async def sum_charges(self, admission_id: int, log_type) -> int:
        return (await self.db.execute(
            select(func.coalesce(func.sum(CareLog.charge), 0))
            .where(CareLog.admission_id == admission_id,
                   CareLog.log_type == log_type))).scalar_one()

    async def count_type(self, admission_id: int, log_type) -> int:
        return (await self.db.execute(
            select(func.count()).select_from(CareLog)
            .where(CareLog.admission_id == admission_id,
                   CareLog.log_type == log_type))).scalar_one()


class TheatreRepository(BaseRepository[OperationTheatre]):
    model = OperationTheatre


class SurgeryRepository(BaseRepository[Surgery]):
    model = Surgery

    def _base(self):
        return (select(Surgery)
                .options(selectinload(Surgery.theatre),
                         selectinload(Surgery.patient),
                         selectinload(Surgery.surgeon)))

    async def get_full(self, id_: int) -> Surgery | None:
        return (await self.db.execute(
            self._base().where(Surgery.id == id_))).scalar_one_or_none()

    async def list_surgeries(self, status: SurgeryStatus | None = None,
                             admission_id: int | None = None,
                             limit: int = 100) -> Sequence[Surgery]:
        stmt = self._base().order_by(Surgery.scheduled_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(Surgery.status == status)
        if admission_id:
            stmt = stmt.where(Surgery.admission_id == admission_id)
        return (await self.db.execute(stmt)).scalars().all()

    async def completed_for_admission(self, admission_id: int) -> Sequence[Surgery]:
        return (await self.db.execute(
            select(Surgery).where(Surgery.admission_id == admission_id,
                                  Surgery.status == SurgeryStatus.COMPLETED)
        )).scalars().all()

    async def on_day(self, day: date) -> Sequence[Surgery]:
        start = datetime.combine(day, datetime.min.time())
        return (await self.db.execute(
            self._base().where(Surgery.scheduled_at >= start,
                               Surgery.scheduled_at < start + timedelta(days=1))
            .order_by(Surgery.scheduled_at))).scalars().all()
