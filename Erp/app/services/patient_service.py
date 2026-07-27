from __future__ import annotations

from datetime import date, datetime, time

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import CONSULTATION_FEES, DEFAULT_CONSULTATION_FEE
from app.core.deps import CurrentUser
from app.core.security import hash_password, validate_password_strength
from app.exceptions import (BusinessRuleError, ConflictError, ForbiddenError,
                            NotFoundError)
from app.models import (Bill, BillItem, Consultation, Patient, PatientDocument,
                        PhysioPlan, PhysioSession, Prescription,
                        PrescriptionItem, Reminder)
from app.models.enums import (AppointmentStatus, BillItemCategory, BillStatus,
                              BillType, ReminderCategory, Role)
from app.repositories.billing import (AppointmentRepository, BillRepository,
                                      ReminderRepository)
from app.repositories.facility import MedicineRepository
from app.repositories.patients import (ConsultationRepository,
                                       DocumentRepository, PatientRepository,
                                       PhysioRepository)
from app.repositories.users import StaffRepository, UserRepository, make_user
from app.schemas.patient import (ConsultationCreate, PatientCreate,
                                 PatientUpdate, PhysioPlanCreate,
                                 PhysioSessionCreate)
from app.utils.files import save_patient_document
from app.utils.ids import bill_number, patient_code


def patient_to_dict(p: Patient) -> dict:
    return {"id": p.id, "patient_code": p.patient_code, "full_name": p.full_name,
            "sex": p.sex.value, "date_of_birth": p.date_of_birth.isoformat(),
            "age": p.age, "blood_group": p.blood_group, "phone": p.phone,
            "email": p.email, "address": p.address,
            "emergency_contact_name": p.emergency_contact_name,
            "emergency_contact_phone": p.emergency_contact_phone,
            "allergies": p.allergies, "medical_history": p.medical_history,
            "created_at": p.created_at.isoformat(), "has_login": p.user_id is not None}


def consultation_to_dict(c: Consultation, bill_id: int | None = None) -> dict:
    rx = None
    if c.prescription:
        rx = {"id": c.prescription.id, "consultation_id": c.id,
              "created_at": c.prescription.created_at.isoformat(),
              "notes": c.prescription.notes, "dispensed": c.prescription.dispensed,
              "dispensed_at": c.prescription.dispensed_at.isoformat()
              if c.prescription.dispensed_at else None,
              "items": [{"id": i.id, "medicine_id": i.medicine_id,
                         "medicine_name": i.medicine_name, "dosage": i.dosage,
                         "frequency": i.frequency, "duration_days": i.duration_days,
                         "quantity": i.quantity, "instructions": i.instructions}
                        for i in c.prescription.items]}
    return {"id": c.id, "patient_id": c.patient_id,
            "patient_name": c.patient.full_name, "patient_code": c.patient.patient_code,
            "doctor_id": c.doctor_id, "doctor_name": c.doctor.full_name,
            "department": c.department.value, "visited_at": c.visited_at.isoformat(),
            "chief_complaint": c.chief_complaint, "diagnosis": c.diagnosis,
            "clinical_notes": c.clinical_notes, "treatments_given": c.treatments_given,
            "fee": c.fee, "follow_up_on": c.follow_up_on.isoformat()
            if c.follow_up_on else None, "prescription": rx, "bill_id": bill_id}


class PatientService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.patients = PatientRepository(db)
        self.users = UserRepository(db)
        self.staff = StaffRepository(db)
        self.consultations = ConsultationRepository(db)
        self.documents = DocumentRepository(db)
        self.physio = PhysioRepository(db)
        self.bills = BillRepository(db)
        self.medicines = MedicineRepository(db)
        self.reminders = ReminderRepository(db)
        self.appointments = AppointmentRepository(db)

    # -------------------------------------------------------------- patients
    async def create_patient(self, data: PatientCreate, actor: CurrentUser) -> dict:
        if await self.patients.by_phone(data.phone):
            raise ConflictError(
                "A patient with this phone number already exists — "
                "search for them instead of creating a duplicate.")
        user_id = None
        if data.create_login:
            if not data.username or not data.password:
                raise BusinessRuleError(
                    "Username and password are required to create portal access.")
            if await self.users.by_username(data.username):
                raise ConflictError(f"Username '{data.username}' is already taken.")
            validate_password_strength(data.password)
            user = await self.users.add(make_user(
                data.username, hash_password(data.password),
                Role.PATIENT, data.full_name))
            user_id = user.id

        seq = await self.patients.next_sequence()
        patient = await self.patients.add(Patient(
            patient_code=patient_code(seq), user_id=user_id,
            created_by_user_id=actor.id,
            **data.model_dump(exclude={"create_login", "username", "password"})))
        await self.db.commit()
        return patient_to_dict(patient)

    async def enable_login(self, patient_id: int, username: str, password: str) -> dict:
        p = await self._get(patient_id)
        if p.user_id:
            raise ConflictError("This patient already has portal access.")
        if await self.users.by_username(username):
            raise ConflictError(f"Username '{username}' is already taken.")
        validate_password_strength(password)
        user = await self.users.add(make_user(
            username, hash_password(password), Role.PATIENT, p.full_name))
        p.user_id = user.id
        await self.db.commit()
        return patient_to_dict(p)

    async def _get(self, patient_id: int) -> Patient:
        p = await self.patients.get(patient_id)
        if p is None:
            raise NotFoundError("Patient not found.")
        return p

    def _assert_can_view(self, patient_id: int, actor: CurrentUser) -> None:
        if actor.role == Role.PATIENT and actor.patient_id != patient_id:
            raise ForbiddenError("You can only view your own records.")

    async def get_patient(self, patient_id: int, actor: CurrentUser) -> dict:
        self._assert_can_view(patient_id, actor)
        return patient_to_dict(await self._get(patient_id))

    async def search(self, q: str) -> list[dict]:
        return [patient_to_dict(p) for p in await self.patients.search(q)]

    async def update_patient(self, patient_id: int, data: PatientUpdate) -> dict:
        p = await self._get(patient_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(p, field, value)
        await self.db.commit()
        return patient_to_dict(p)

    # --------------------------------------------------------- consultations
    async def create_consultation(self, data: ConsultationCreate,
                                  actor: CurrentUser) -> dict:
        """Doctors (super admins) record the visit while consulting; an OPD
        bill is opened automatically with the consultation fee."""
        patient = await self._get(data.patient_id)
        doctor = await self.staff.by_user_id(actor.id)
        if doctor is None:
            raise ForbiddenError("Only doctors can record consultations.")

        fee = data.fee
        if fee is None:
            fee = CONSULTATION_FEES.get(actor.username, DEFAULT_CONSULTATION_FEE)

        consult = await self.consultations.add(Consultation(
            patient_id=patient.id, doctor_id=doctor.id,
            appointment_id=data.appointment_id, department=data.department,
            chief_complaint=data.chief_complaint, diagnosis=data.diagnosis,
            clinical_notes=data.clinical_notes,
            treatments_given=data.treatments_given, fee=fee,
            follow_up_on=data.follow_up_on))

        if data.prescription_items or data.prescription_notes:
            rx = Prescription(
                consultation_id=consult.id, patient_id=patient.id,
                doctor_id=doctor.id, notes=data.prescription_notes)
            self.db.add(rx)
            await self.db.flush()
            for item in data.prescription_items:
                name = item.medicine_name
                if item.medicine_id:
                    med = await self.medicines.get(item.medicine_id)
                    if med is None:
                        raise NotFoundError(f"Medicine id {item.medicine_id} not found.")
                    name = med.name
                self.db.add(PrescriptionItem(
                    prescription_id=rx.id, medicine_id=item.medicine_id,
                    medicine_name=name, dosage=item.dosage,
                    frequency=item.frequency, duration_days=item.duration_days,
                    quantity=item.quantity, instructions=item.instructions))
            await self.db.flush()

        # OPD bill with the consultation fee
        bill = await self.bills.add(Bill(
            bill_number=bill_number(), bill_type=BillType.OPD,
            patient_id=patient.id, consultation_id=consult.id,
            subtotal=fee, total=fee))
        self.db.add(BillItem(bill_id=bill.id, category=BillItemCategory.CONSULTATION,
                             description=f"Consultation — {doctor.full_name}",
                             quantity=1, unit_price=fee, amount=fee))

        # link appointment → COMPLETED
        if data.appointment_id:
            appt = await self.appointments.get(data.appointment_id)
            if appt:
                appt.status = AppointmentStatus.COMPLETED
                if appt.patient_id is None:
                    appt.patient_id = patient.id

        # follow-up reminder
        if data.follow_up_on:
            self.db.add(Reminder(
                title=f"Follow-up: {patient.full_name}",
                message=f"{patient.patient_code} · follow-up for "
                        f"“{data.chief_complaint[:80]}” with {doctor.full_name}.",
                category=ReminderCategory.FOLLOW_UP, patient_id=patient.id,
                due_at=datetime.combine(data.follow_up_on, time(10, 0)),
                created_by_user_id=actor.id))

        await self.db.commit()
        full = await self.consultations.get_full(consult.id)
        return consultation_to_dict(full, bill.id)

    async def list_consultations(self, actor: CurrentUser,
                                 patient_id: int | None = None,
                                 day: date | None = None) -> list[dict]:
        if actor.role == Role.PATIENT:
            patient_id = actor.patient_id
        if patient_id:
            rows = await self.consultations.for_patient(patient_id)
        elif day:
            rows = await self.consultations.on_day(day)
        else:
            rows = await self.consultations.recent()
        out = []
        for c in rows:
            bill = await self.bills.for_consultation(c.id)
            out.append(consultation_to_dict(c, bill.id if bill else None))
        return out

    async def get_consultation(self, consultation_id: int, actor: CurrentUser) -> dict:
        c = await self.consultations.get_full(consultation_id)
        if c is None:
            raise NotFoundError("Consultation not found.")
        self._assert_can_view(c.patient_id, actor)
        bill = await self.bills.for_consultation(c.id)
        return consultation_to_dict(c, bill.id if bill else None)

    # ------------------------------------------------------------- documents
    async def upload_document(self, patient_id: int, upload: UploadFile,
                              doc_type, title: str, taken_on: date | None,
                              notes: str, actor: CurrentUser) -> PatientDocument:
        patient = await self._get(patient_id)
        rel, ctype, size = await save_patient_document(patient.id, upload)
        doc = await self.documents.add(PatientDocument(
            patient_id=patient.id, doc_type=doc_type, title=title,
            file_path=rel, original_name=upload.filename or "file",
            content_type=ctype, size_bytes=size, taken_on=taken_on,
            notes=notes, uploaded_by_user_id=actor.id))
        await self.db.commit()
        return doc

    async def list_documents(self, patient_id: int, actor: CurrentUser):
        self._assert_can_view(patient_id, actor)
        await self._get(patient_id)
        return await self.documents.for_patient(patient_id)

    async def get_document(self, doc_id: int, actor: CurrentUser) -> PatientDocument:
        doc = await self.documents.get(doc_id)
        if doc is None:
            raise NotFoundError("Document not found.")
        self._assert_can_view(doc.patient_id, actor)
        return doc

    # ---------------------------------------------------------------- physio
    def _plan_to_dict(self, plan: PhysioPlan) -> dict:
        return {"id": plan.id, "patient_id": plan.patient_id,
                "patient_name": plan.patient.full_name,
                "prescribed_by_name": plan.prescribed_by.full_name,
                "prescribed_on": plan.prescribed_on.isoformat(),
                "days_count": plan.days_count,
                "exercises": [e for e in plan.exercises.split("; ") if e],
                "modalities": [m for m in plan.modalities.split("; ") if m],
                "traction": [t for t in plan.traction.split("; ") if t],
                "notes": plan.notes, "is_active": plan.is_active,
                "sessions_done": len(plan.sessions),
                "sessions": [{"id": s.id, "plan_id": s.plan_id,
                              "session_date": s.session_date.isoformat(),
                              "timing": s.timing, "amount": s.amount,
                              "notes": s.notes,
                              "performed_by_name": s.performed_by.full_name}
                             for s in sorted(plan.sessions,
                                             key=lambda x: x.session_date,
                                             reverse=True)]}

    async def create_physio_plan(self, data: PhysioPlanCreate,
                                 actor: CurrentUser) -> dict:
        await self._get(data.patient_id)
        prescriber = await self.staff.by_user_id(actor.id)
        if prescriber is None:
            raise ForbiddenError("Only hospital staff can prescribe physiotherapy.")
        plan = await self.physio.add(PhysioPlan(
            patient_id=data.patient_id, prescribed_by_id=prescriber.id,
            days_count=data.days_count,
            exercises="; ".join(e.value for e in data.exercises),
            modalities="; ".join(m.value for m in data.modalities),
            traction="; ".join(t.value for t in data.traction),
            notes=data.notes))
        await self.db.commit()
        full = await self.physio.get_full(plan.id)
        return self._plan_to_dict(full)

    async def add_physio_session(self, data: PhysioSessionCreate,
                                 actor: CurrentUser) -> dict:
        plan = await self.physio.get_full(data.plan_id)
        if plan is None:
            raise NotFoundError("Physiotherapy plan not found.")
        if not plan.is_active:
            raise BusinessRuleError("This plan is closed — no more sessions can be added.")
        performer = await self.staff.by_user_id(actor.id)
        if performer is None:
            raise ForbiddenError("Only hospital staff can record sessions.")
        if len(plan.sessions) >= plan.days_count:
            raise BusinessRuleError(
                f"All {plan.days_count} prescribed sessions are already recorded. "
                "Ask the doctor to extend the plan.")
        self.db.add(PhysioSession(
            plan_id=plan.id, session_date=data.session_date, timing=data.timing,
            amount=data.amount, performed_by_id=performer.id, notes=data.notes))
        await self.db.flush()
        if len(plan.sessions) + 1 >= plan.days_count:
            plan.is_active = False
        await self.db.commit()
        full = await self.physio.get_full(plan.id)
        return self._plan_to_dict(full)

    async def list_physio_plans(self, actor: CurrentUser,
                                patient_id: int | None = None) -> list[dict]:
        if actor.role == Role.PATIENT:
            patient_id = actor.patient_id
        plans = await self.physio.list_plans(patient_id)
        return [self._plan_to_dict(p) for p in plans]
