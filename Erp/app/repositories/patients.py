from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.models import (Consultation, Patient, PatientDocument, PhysioPlan,
                        PhysioSession, Prescription, Staff)
from app.repositories.base import BaseRepository


class PatientRepository(BaseRepository[Patient]):
    model = Patient

    async def next_sequence(self) -> int:
        return ((await self.db.execute(select(func.max(Patient.id)))).scalar() or 0) + 1

    async def by_code(self, code: str) -> Patient | None:
        return (await self.db.execute(
            select(Patient).where(Patient.patient_code == code))).scalar_one_or_none()

    async def by_phone(self, phone: str) -> Patient | None:
        return (await self.db.execute(
            select(Patient).where(Patient.phone == phone))).scalar_one_or_none()

    async def search(self, q: str = "", limit: int = 50) -> Sequence[Patient]:
        stmt = select(Patient).order_by(Patient.created_at.desc()).limit(limit)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Patient.full_name.ilike(like),
                                  Patient.patient_code.ilike(like),
                                  Patient.phone.like(like)))
        return (await self.db.execute(stmt)).scalars().all()


class ConsultationRepository(BaseRepository[Consultation]):
    model = Consultation

    def _base(self):
        return (select(Consultation)
                .options(selectinload(Consultation.prescription)
                         .selectinload(Prescription.items),
                         selectinload(Consultation.patient),
                         selectinload(Consultation.doctor)))

    async def get_full(self, id_: int) -> Consultation | None:
        return (await self.db.execute(
            self._base().where(Consultation.id == id_))).scalar_one_or_none()

    async def for_patient(self, patient_id: int) -> Sequence[Consultation]:
        return (await self.db.execute(
            self._base().where(Consultation.patient_id == patient_id)
            .order_by(Consultation.visited_at.desc()))).scalars().all()

    async def on_day(self, day: date) -> Sequence[Consultation]:
        start = datetime.combine(day, datetime.min.time())
        return (await self.db.execute(
            self._base()
            .where(Consultation.visited_at >= start,
                   Consultation.visited_at < start + timedelta(days=1))
            .order_by(Consultation.visited_at.desc()))).scalars().all()

    async def recent(self, limit: int = 30) -> Sequence[Consultation]:
        return (await self.db.execute(
            self._base().order_by(Consultation.visited_at.desc()).limit(limit)
        )).scalars().all()

    async def followups_between(self, start: date, end: date) -> Sequence[Consultation]:
        return (await self.db.execute(
            self._base().where(Consultation.follow_up_on.is_not(None),
                               Consultation.follow_up_on >= start,
                               Consultation.follow_up_on <= end)
            .order_by(Consultation.follow_up_on))).scalars().all()


class PrescriptionRepository(BaseRepository[Prescription]):
    model = Prescription

    async def get_full(self, id_: int) -> Prescription | None:
        return (await self.db.execute(
            select(Prescription)
            .options(selectinload(Prescription.items))
            .where(Prescription.id == id_))).scalar_one_or_none()

    async def pending_dispense(self) -> Sequence[tuple[Prescription, str, str]]:
        return (await self.db.execute(
            select(Prescription, Patient.full_name, Patient.patient_code)
            .join(Patient, Prescription.patient_id == Patient.id)
            .options(selectinload(Prescription.items))
            .where(Prescription.dispensed.is_(False))
            .order_by(Prescription.created_at.desc()))).all()


class DocumentRepository(BaseRepository[PatientDocument]):
    model = PatientDocument

    async def for_patient(self, patient_id: int) -> Sequence[PatientDocument]:
        return (await self.db.execute(
            select(PatientDocument)
            .where(PatientDocument.patient_id == patient_id)
            .order_by(PatientDocument.uploaded_at.desc()))).scalars().all()


class PhysioRepository(BaseRepository[PhysioPlan]):
    model = PhysioPlan

    def _base(self):
        return (select(PhysioPlan)
                .options(selectinload(PhysioPlan.sessions)
                         .selectinload(PhysioSession.performed_by),
                         selectinload(PhysioPlan.patient),
                         selectinload(PhysioPlan.prescribed_by)))

    async def get_full(self, id_: int) -> PhysioPlan | None:
        return (await self.db.execute(
            self._base().where(PhysioPlan.id == id_))).scalar_one_or_none()

    async def list_plans(self, patient_id: int | None = None,
                         active_only: bool = False) -> Sequence[PhysioPlan]:
        stmt = self._base().order_by(PhysioPlan.prescribed_on.desc())
        if patient_id:
            stmt = stmt.where(PhysioPlan.patient_id == patient_id)
        if active_only:
            stmt = stmt.where(PhysioPlan.is_active.is_(True))
        return (await self.db.execute(stmt)).scalars().all()

    async def sessions_on(self, day: date) -> int:
        return (await self.db.execute(
            select(func.count()).select_from(PhysioSession)
            .where(PhysioSession.session_date == day))).scalar_one()
