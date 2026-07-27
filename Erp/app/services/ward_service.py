from __future__ import annotations

import json
import math
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (ADMISSION_CHARGE, DOCTOR_VISIT_CHARGE,
                                EMERGENCY_CHARGE, NURSING_CHARGE_PER_DAY,
                                OT_BASE_CHARGES)
from app.core.deps import CurrentUser
from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models import (Admission, Bill, BillItem, CareLog, Mediclaim,
                        Reminder, Room, Surgery)
from app.models.enums import (AdmissionStatus, AdmissionType, BillItemCategory,
                              BillStatus, BillType, CareLogType, ClaimStatus,
                              OTStatus, ReminderCategory, RoomStatus,
                              StockTxnType, SurgeryStatus)
from app.repositories.billing import BillRepository, MediclaimRepository
from app.repositories.facility import (AdmissionRepository, CareLogRepository,
                                       MedicineRepository, RoomRepository,
                                       SurgeryRepository, TheatreRepository)
from app.repositories.patients import PatientRepository
from app.repositories.users import StaffRepository
from app.schemas.operations import (AdmissionCreate, CareLogCreate,
                                    DischargeIn, RoomCreate, RoomUpdate,
                                    SurgeryCreate, SurgeryStatusIn)
from app.services.pharmacy_service import PharmacyService
from app.utils.ids import bill_number, claim_number


def admission_to_dict(a: Admission, bill_id: int | None = None,
                      claim: str | None = None) -> dict:
    ref = a.discharged_at or datetime.now()
    hours = round((ref - a.admitted_at).total_seconds() / 3600, 1)
    return {"id": a.id, "patient_id": a.patient_id,
            "patient_name": a.patient.full_name,
            "patient_code": a.patient.patient_code,
            "room_id": a.room_id, "room_number": a.room.room_number,
            "room_type": a.room.room_type.value,
            "primary_doctor_id": a.primary_doctor_id,
            "doctor_name": a.primary_doctor.full_name,
            "nurse_name": a.assigned_nurse.full_name if a.assigned_nurse else None,
            "admission_type": a.admission_type.value, "reason": a.reason,
            "diagnosis": a.diagnosis, "admitted_at": a.admitted_at.isoformat(),
            "discharged_at": a.discharged_at.isoformat() if a.discharged_at else None,
            "status": a.status.value, "discharge_summary": a.discharge_summary,
            "bill_id": bill_id, "claim_number": claim, "hours_admitted": hours}


def surgery_to_dict(s: Surgery) -> dict:
    return {"id": s.id, "theatre_id": s.theatre_id, "theatre_name": s.theatre.name,
            "patient_id": s.patient_id, "patient_name": s.patient.full_name,
            "admission_id": s.admission_id, "surgeon_id": s.surgeon_id,
            "surgeon_name": s.surgeon.full_name, "name": s.name,
            "scheduled_at": s.scheduled_at.isoformat(),
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "status": s.status.value, "equipment_used": s.equipment_used,
            "charges": s.charges, "notes": s.notes}


class WardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rooms = RoomRepository(db)
        self.admissions = AdmissionRepository(db)
        self.care_logs = CareLogRepository(db)
        self.patients = PatientRepository(db)
        self.staff = StaffRepository(db)
        self.medicines = MedicineRepository(db)
        self.bills = BillRepository(db)
        self.claims = MediclaimRepository(db)
        self.theatres = TheatreRepository(db)
        self.surgeries = SurgeryRepository(db)
        self.pharmacy = PharmacyService(db)

    # ----------------------------------------------------------------- rooms
    async def create_room(self, data: RoomCreate) -> Room:
        if await self.rooms.by_number(data.room_number):
            raise ConflictError(f"Room {data.room_number} already exists.")
        room = await self.rooms.add(Room(**data.model_dump()))
        await self.db.commit()
        return room

    async def update_room(self, room_id: int, data: RoomUpdate) -> Room:
        room = await self.rooms.get(room_id)
        if room is None:
            raise NotFoundError("Room not found.")
        if data.status is not None:
            if room.status == RoomStatus.OCCUPIED:
                raise BusinessRuleError(
                    "This room is occupied — discharge the patient first.")
            if data.status == RoomStatus.OCCUPIED:
                raise BusinessRuleError(
                    "Rooms become occupied through admissions, not manually.")
            room.status = data.status
        for field in ("daily_rate", "floor", "notes"):
            value = getattr(data, field)
            if value is not None:
                setattr(room, field, value)
        await self.db.commit()
        return room

    async def room_board(self) -> list[dict]:
        out = []
        for (room, adm_id, admitted_at, pid, pname,
             doctor_name, nurse_name) in await self.rooms.board():
            out.append({"id": room.id, "room_number": room.room_number,
                        "room_type": room.room_type.value,
                        "daily_rate": room.daily_rate,
                        "status": room.status.value, "floor": room.floor,
                        "notes": room.notes, "admission_id": adm_id,
                        "occupant_patient_id": pid, "occupant_name": pname,
                        "admitted_at": admitted_at.isoformat() if admitted_at else None,
                        "doctor_name": doctor_name, "nurse_name": nurse_name})
        return out

    # ------------------------------------------------------------ admissions
    async def admit(self, data: AdmissionCreate, actor: CurrentUser) -> dict:
        patient = await self.patients.get(data.patient_id)
        if patient is None:
            raise NotFoundError("Patient not found.")
        if await self.admissions.active_for_patient(patient.id):
            raise ConflictError(f"{patient.full_name} is already admitted.")
        room = await self.rooms.get(data.room_id)
        if room is None:
            raise NotFoundError("Room not found.")
        if room.status != RoomStatus.AVAILABLE:
            raise ConflictError(f"Room {room.room_number} is not available.")
        if await self.staff.get(data.primary_doctor_id) is None:
            raise NotFoundError("Primary doctor not found.")
        admitted_at = data.admitted_at or datetime.now()
        if admitted_at > datetime.now():
            raise BusinessRuleError("Admission time cannot be in the future.")

        admission = await self.admissions.add(Admission(
            patient_id=patient.id, room_id=room.id,
            primary_doctor_id=data.primary_doctor_id,
            assigned_nurse_id=data.assigned_nurse_id,
            admission_type=data.admission_type, reason=data.reason,
            diagnosis=data.diagnosis, admitted_at=admitted_at,
            created_by_user_id=actor.id))
        room.status = RoomStatus.OCCUPIED

        # Mediclaim file opens automatically at admission
        claim = Mediclaim(claim_number=claim_number(), admission_id=admission.id,
                          patient_id=patient.id)
        self.db.add(claim)

        # Reminder for the desk / doctors
        is_emergency = data.admission_type == AdmissionType.EMERGENCY
        self.db.add(Reminder(
            title=("⚠ Emergency admission — " if is_emergency else "Admitted — ")
                  + patient.full_name,
            message=f"{patient.patient_code} in room {room.room_number} · "
                    f"{data.reason[:120]}",
            category=(ReminderCategory.EMERGENCY if is_emergency
                      else ReminderCategory.ADMISSION),
            patient_id=patient.id, admission_id=admission.id,
            due_at=datetime.now(), created_by_user_id=actor.id))

        await self.db.commit()
        full = await self.admissions.get_full(admission.id)
        return admission_to_dict(full, claim=claim.claim_number)

    async def list_admissions(self, status: AdmissionStatus | None = None,
                              patient_id: int | None = None) -> list[dict]:
        out = []
        for a in await self.admissions.list_admissions(status, patient_id):
            bill = await self.bills.for_admission(a.id)
            claim = await self.claims.for_admission(a.id)
            out.append(admission_to_dict(a, bill.id if bill else None,
                                         claim.claim_number if claim else None))
        return out

    async def get_admission(self, admission_id: int) -> dict:
        a = await self.admissions.get_full(admission_id)
        if a is None:
            raise NotFoundError("Admission not found.")
        bill = await self.bills.for_admission(a.id)
        claim = await self.claims.for_admission(a.id)
        d = admission_to_dict(a, bill.id if bill else None,
                              claim.claim_number if claim else None)
        d["care_logs"] = await self.list_care_logs(admission_id)
        d["surgeries"] = [surgery_to_dict(s) for s in
                          await self.surgeries.list_surgeries(admission_id=admission_id)]
        return d

    # ------------------------------------------------------------- care logs
    async def add_care_log(self, data: CareLogCreate, actor: CurrentUser) -> dict:
        admission = await self.admissions.get_full(data.admission_id)
        if admission is None:
            raise NotFoundError("Admission not found.")
        if admission.status != AdmissionStatus.ADMITTED:
            raise BusinessRuleError(
                "This patient is discharged — the care timeline is closed.")

        charge = data.charge
        if data.log_type == CareLogType.MEDICATION:
            if not data.medicine_id or data.quantity <= 0:
                raise BusinessRuleError(
                    "Pick the medicine and a quantity for a medication entry.")
            med = await self.medicines.get(data.medicine_id)
            if med is None:
                raise NotFoundError("Medicine not found.")
            await self.pharmacy._move_stock(
                med, StockTxnType.OUT, data.quantity,
                f"Ward · admission #{admission.id}", actor.id)
            charge = med.unit_price * data.quantity
        elif data.log_type == CareLogType.DOCTOR_VISIT:
            if not data.doctor_id:
                raise BusinessRuleError("Select which doctor visited.")
            if await self.staff.get(data.doctor_id) is None:
                raise NotFoundError("Doctor not found.")
            charge = DOCTOR_VISIT_CHARGE

        log = await self.care_logs.add(CareLog(
            admission_id=admission.id, log_type=data.log_type,
            description=data.description, medicine_id=data.medicine_id,
            quantity=data.quantity, charge=charge, doctor_id=data.doctor_id,
            logged_by_user_id=actor.id))
        await self.db.commit()
        return {"id": log.id, "charge": charge}

    async def list_care_logs(self, admission_id: int) -> list[dict]:
        rows = await self.care_logs.for_admission(admission_id)
        return [{"id": log.id, "admission_id": log.admission_id,
                 "log_type": log.log_type.value, "description": log.description,
                 "medicine_name": med_name, "quantity": log.quantity,
                 "charge": log.charge, "doctor_name": doc_name,
                 "logged_at": log.logged_at.isoformat(), "logged_by": by_name}
                for log, med_name, doc_name, by_name in rows]

    # ------------------------------------------------- discharge & billing
    async def discharge(self, admission_id: int, data: DischargeIn,
                        actor: CurrentUser) -> dict:
        """Close the stay: compute the bill from hours × room, doctor visits,
        OT charges, medicines and services; free the room; finalize the
        mediclaim; raise a discharge reminder."""
        a = await self.admissions.get_full(admission_id)
        if a is None:
            raise NotFoundError("Admission not found.")
        if a.status == AdmissionStatus.DISCHARGED:
            raise ConflictError("This patient is already discharged.")

        now = datetime.now()
        total_hours = max(1, math.ceil((now - a.admitted_at).total_seconds() / 3600))
        billable_days = math.ceil(total_hours / 24)

        bill = await self.bills.add(Bill(
            bill_number=bill_number(), bill_type=BillType.IPD,
            patient_id=a.patient_id, admission_id=a.id,
            notes=f"Stay of {total_hours} h across {billable_days} day(s)"))

        items_snapshot: list[dict] = []

        def add_item(category, description, qty, unit_price):
            amount = qty * unit_price
            self.db.add(BillItem(bill_id=bill.id, category=category,
                                 description=description, quantity=qty,
                                 unit_price=unit_price, amount=amount))
            items_snapshot.append({"category": category.value,
                                   "description": description,
                                   "quantity": qty, "amount": amount})
            return amount

        subtotal = 0
        subtotal += add_item(BillItemCategory.ADMISSION,
                             "Admission & registration", 1, ADMISSION_CHARGE)
        if a.admission_type == AdmissionType.EMERGENCY:
            subtotal += add_item(BillItemCategory.EMERGENCY,
                                 "Emergency / casualty care", 1, EMERGENCY_CHARGE)
        subtotal += add_item(
            BillItemCategory.ROOM,
            f"Room {a.room.room_number} ({a.room.room_type.value}) · "
            f"{total_hours} h", billable_days, a.room.daily_rate)
        subtotal += add_item(BillItemCategory.NURSING, "Nursing care",
                             billable_days, NURSING_CHARGE_PER_DAY)

        visits = await self.care_logs.count_type(a.id, CareLogType.DOCTOR_VISIT)
        if visits:
            subtotal += add_item(BillItemCategory.DOCTOR_VISIT,
                                 "Doctor ward visits", visits, DOCTOR_VISIT_CHARGE)

        med_total = await self.care_logs.sum_charges(a.id, CareLogType.MEDICATION)
        if med_total:
            subtotal += add_item(BillItemCategory.MEDICINE,
                                 "Medicines administered in ward", 1, med_total)

        for cat, log_type, label in (
                (BillItemCategory.TREATMENT, CareLogType.TREATMENT,
                 "Treatments & procedures"),
                (BillItemCategory.SERVICE, CareLogType.SERVICE,
                 "Services & facilities")):
            amt = await self.care_logs.sum_charges(a.id, log_type)
            if amt:
                subtotal += add_item(cat, label, 1, amt)

        for s in await self.surgeries.completed_for_admission(a.id):
            subtotal += add_item(BillItemCategory.OT,
                                 f"Operation theatre — {s.name}", 1, s.charges)

        if data.discount > subtotal:
            raise BusinessRuleError("Discount cannot exceed the bill subtotal.")
        bill.subtotal = subtotal
        bill.discount = data.discount
        bill.total = subtotal - data.discount

        # close the stay
        a.status = AdmissionStatus.DISCHARGED
        a.discharged_at = now
        a.discharge_summary = data.discharge_summary
        a.room.status = RoomStatus.AVAILABLE

        # finalize the mediclaim with a frozen summary
        claim = await self.claims.for_admission(a.id)
        if claim and claim.status == ClaimStatus.DRAFT:
            claim.status = ClaimStatus.FINALIZED
            claim.finalized_at = now
            claim.summary_json = json.dumps({
                "patient": {"code": a.patient.patient_code,
                            "name": a.patient.full_name, "age": a.patient.age,
                            "sex": a.patient.sex.value},
                "admission": {"type": a.admission_type.value, "reason": a.reason,
                              "diagnosis": a.diagnosis,
                              "admitted_at": a.admitted_at.isoformat(),
                              "discharged_at": now.isoformat(),
                              "hours": total_hours,
                              "room": f"{a.room.room_number} "
                                      f"({a.room.room_type.value})",
                              "primary_doctor": a.primary_doctor.full_name},
                "bill": {"number": bill.bill_number, "subtotal": bill.subtotal,
                         "discount": bill.discount, "total": bill.total,
                         "items": items_snapshot},
                "discharge_summary": data.discharge_summary,
            }, indent=2)

        self.db.add(Reminder(
            title=f"Discharged — {a.patient.full_name}",
            message=f"{a.patient.patient_code} discharged from room "
                    f"{a.room.room_number}. Bill {bill.bill_number} "
                    f"₹{bill.total:,} pending.",
            category=ReminderCategory.DISCHARGE, patient_id=a.patient_id,
            admission_id=a.id, due_at=now, created_by_user_id=actor.id))

        await self.db.commit()
        full = await self.admissions.get_full(a.id)
        return admission_to_dict(full, bill.id,
                                 claim.claim_number if claim else None)

    # -------------------------------------------------------------------- OT
    async def list_theatres(self) -> list:
        return list(await self.theatres.list_all(self.theatres.model.name))

    async def schedule_surgery(self, data: SurgeryCreate,
                               actor: CurrentUser) -> dict:
        theatre = await self.theatres.get(data.theatre_id)
        if theatre is None:
            raise NotFoundError("Operation theatre not found.")
        if theatre.status == OTStatus.MAINTENANCE:
            raise BusinessRuleError(f"{theatre.name} is under maintenance.")
        if await self.patients.get(data.patient_id) is None:
            raise NotFoundError("Patient not found.")
        if await self.staff.get(data.surgeon_id) is None:
            raise NotFoundError("Surgeon not found.")
        if data.admission_id:
            adm = await self.admissions.get(data.admission_id)
            if adm is None:
                raise NotFoundError("Admission not found.")
            if adm.patient_id != data.patient_id:
                raise BusinessRuleError(
                    "The admission belongs to a different patient.")
        charges = data.charges
        if charges is None:
            charges = OT_BASE_CHARGES[theatre.category.value]
        surgery = await self.surgeries.add(Surgery(
            theatre_id=theatre.id, patient_id=data.patient_id,
            admission_id=data.admission_id, surgeon_id=data.surgeon_id,
            name=data.name, scheduled_at=data.scheduled_at, charges=charges,
            equipment_used=data.equipment_used, notes=data.notes))
        await self.db.commit()
        full = await self.surgeries.get_full(surgery.id)
        return surgery_to_dict(full)

    async def set_surgery_status(self, surgery_id: int, data: SurgeryStatusIn,
                                 actor: CurrentUser) -> dict:
        s = await self.surgeries.get_full(surgery_id)
        if s is None:
            raise NotFoundError("Surgery not found.")
        allowed = {SurgeryStatus.SCHEDULED: {SurgeryStatus.IN_PROGRESS,
                                             SurgeryStatus.CANCELLED},
                   SurgeryStatus.IN_PROGRESS: {SurgeryStatus.COMPLETED},
                   SurgeryStatus.COMPLETED: set(),
                   SurgeryStatus.CANCELLED: set()}
        if data.status not in allowed[s.status]:
            raise BusinessRuleError(
                f"Cannot move a {s.status.value.lower().replace('_', ' ')} "
                f"surgery to {data.status.value.lower().replace('_', ' ')}.")

        now = datetime.now()
        if data.status == SurgeryStatus.IN_PROGRESS:
            s.started_at = now
            s.theatre.status = OTStatus.OCCUPIED
        elif data.status in (SurgeryStatus.COMPLETED, SurgeryStatus.CANCELLED):
            if data.status == SurgeryStatus.COMPLETED:
                s.ended_at = now
            s.theatre.status = OTStatus.AVAILABLE
        s.status = data.status
        if data.equipment_used is not None:
            s.equipment_used = data.equipment_used
        if data.notes is not None:
            s.notes = data.notes
        if data.charges is not None:
            s.charges = data.charges

        bill_id = None
        # day-care surgery without admission → standalone bill on completion
        if data.status == SurgeryStatus.COMPLETED and s.admission_id is None:
            bill = await self.bills.add(Bill(
                bill_number=bill_number(), bill_type=BillType.SURGERY,
                patient_id=s.patient_id, surgery_id=s.id,
                subtotal=s.charges, total=s.charges))
            self.db.add(BillItem(bill_id=bill.id, category=BillItemCategory.OT,
                                 description=f"Operation theatre — {s.name}",
                                 quantity=1, unit_price=s.charges,
                                 amount=s.charges))
            bill_id = bill.id

        await self.db.commit()
        out = surgery_to_dict(s)
        out["bill_id"] = bill_id
        return out

    async def list_surgeries(self, status: SurgeryStatus | None = None) -> list[dict]:
        return [surgery_to_dict(s)
                for s in await self.surgeries.list_surgeries(status)]
