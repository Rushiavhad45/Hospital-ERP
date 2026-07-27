from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.exceptions import (BusinessRuleError, ConflictError, ForbiddenError,
                            NotFoundError)
from app.models import Appointment
from app.models.enums import (AppointmentStatus, BookedVia, Department,
                              Designation, Role)
from app.repositories.billing import AppointmentRepository
from app.repositories.patients import PatientRepository
from app.repositories.users import StaffRepository
from app.schemas.operations import GuestAppointmentIn, PortalAppointmentIn
from app.utils.ids import appointment_code
from app.utils.timeslots import generate_slots, validate_booking_date

_DEPT_BY_STAFF_DEPT = {
    "ORTHOPAEDICS": Department.ORTHOPAEDICS,
    "OPHTHALMOLOGY": Department.OPHTHALMOLOGY,
    "PHYSIOTHERAPY": Department.PHYSIOTHERAPY,
}


def appointment_to_dict(a: Appointment) -> dict:
    return {"id": a.id, "code": a.code, "patient_id": a.patient_id,
            "patient_name": a.patient.full_name if a.patient else a.guest_name,
            "phone": a.patient.phone if a.patient else a.guest_phone,
            "doctor_id": a.doctor_id, "doctor_name": a.doctor.full_name,
            "department": a.department.value,
            "appointment_date": a.appointment_date.isoformat(), "slot": a.slot,
            "reason": a.reason, "status": a.status.value,
            "booked_via": a.booked_via.value,
            "created_at": a.created_at.isoformat(),
            "confirmed_at": a.confirmed_at.isoformat() if a.confirmed_at else None}


class AppointmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.appointments = AppointmentRepository(db)
        self.staff = StaffRepository(db)
        self.patients = PatientRepository(db)

    async def _doctor(self, doctor_id: int):
        doc = await self.staff.get(doctor_id)
        if doc is None or doc.designation != Designation.DOCTOR or not doc.is_active:
            raise NotFoundError("Doctor not found.")
        return doc

    async def available_slots(self, doctor_id: int, on: date) -> dict:
        doc = await self._doctor(doctor_id)
        today = date.today()
        if on not in (today, today + timedelta(days=1)):
            raise BusinessRuleError(
                "Appointments can be booked for today or tomorrow only.")
        all_slots = generate_slots(doc.shift_start, doc.shift_end, on)
        booked = set(await self.appointments.booked_slots(doctor_id, on))
        return {"doctor_id": doctor_id, "doctor_name": doc.full_name,
                "date": on.isoformat(),
                "closed": on.weekday() == 6,
                "slots": [{"slot": s, "available": s not in booked}
                          for s in all_slots]}

    async def _book(self, *, doctor_id: int, on: date, slot: str, reason: str,
                    patient_id: int | None, guest_name: str, guest_phone: str,
                    via: BookedVia) -> Appointment:
        doc = await self._doctor(doctor_id)
        validate_booking_date(on)
        if slot not in generate_slots(doc.shift_start, doc.shift_end, on):
            raise BusinessRuleError(
                "That time is outside the doctor's OPD hours (or already past).")
        if await self.appointments.slot_taken(doctor_id, on, slot):
            raise ConflictError("That slot has just been taken — pick another one.")
        # A CANCELLED / NO_SHOW row still occupies the (doctor, date, slot)
        # unique key at the DB level even though the slot is genuinely free —
        # repurpose that row instead of inserting a duplicate.
        stale = await self.appointments.inactive_for_slot(doctor_id, on, slot)
        if stale is not None:
            stale.code = appointment_code()
            stale.patient_id = patient_id
            stale.guest_name = guest_name
            stale.guest_phone = guest_phone
            stale.reason = reason
            stale.booked_via = via
            stale.status = AppointmentStatus.BOOKED
            stale.created_at = datetime.now()
            stale.confirmed_at = None
            stale.confirmed_by_user_id = None
            await self.db.commit()
            return stale
        appt = await self.appointments.add(Appointment(
            code=appointment_code(), patient_id=patient_id,
            guest_name=guest_name, guest_phone=guest_phone, doctor_id=doctor_id,
            department=_DEPT_BY_STAFF_DEPT.get(doc.department, Department.GENERAL),
            appointment_date=on, slot=slot, reason=reason, booked_via=via))
        await self.db.commit()
        return appt

    async def book_guest(self, data: GuestAppointmentIn) -> dict:
        """Public booking — no login needed. If the phone matches a registered
        patient, the booking is linked to their file automatically."""
        existing = await self.patients.by_phone(data.phone)
        appt = await self._book(
            doctor_id=data.doctor_id, on=data.appointment_date, slot=data.slot,
            reason=data.reason, patient_id=existing.id if existing else None,
            guest_name=data.name, guest_phone=data.phone, via=BookedVia.GUEST)
        full = await self.appointments.get_full(appt.id)
        out = appointment_to_dict(full)
        out["note"] = ("Please arrive 30 minutes before your slot; the front "
                       "desk will confirm your appointment on arrival.")
        return out

    async def book_portal(self, data: PortalAppointmentIn,
                          actor: CurrentUser) -> dict:
        appt = await self._book(
            doctor_id=data.doctor_id, on=data.appointment_date, slot=data.slot,
            reason=data.reason, patient_id=actor.patient_id,
            guest_name="", guest_phone="", via=BookedVia.PORTAL)
        full = await self.appointments.get_full(appt.id)
        return appointment_to_dict(full)

    async def track_guest(self, code: str, phone: str) -> dict:
        appt = await self.appointments.by_code_phone(code, phone)
        if appt is None:
            raise NotFoundError("No appointment found for that code.")
        stored_phone = appt.patient.phone if appt.patient else appt.guest_phone
        if stored_phone != phone:
            raise NotFoundError("No appointment found for that code.")
        return appointment_to_dict(appt)

    async def list_appointments(self, actor: CurrentUser,
                                day: date | None = None,
                                span_days: int = 1) -> list[dict]:
        if actor.role == Role.PATIENT:
            rows = await self.appointments.for_patient(actor.patient_id)
        else:
            start = day or date.today()
            rows = await self.appointments.list_between(
                start, start + timedelta(days=span_days - 1))
        return [appointment_to_dict(a) for a in rows]

    async def set_status(self, appointment_id: int, status: AppointmentStatus,
                         actor: CurrentUser) -> dict:
        a = await self.appointments.get_full(appointment_id)
        if a is None:
            raise NotFoundError("Appointment not found.")

        if actor.role == Role.PATIENT:
            if a.patient_id != actor.patient_id:
                raise ForbiddenError("This appointment is not yours.")
            if status != AppointmentStatus.CANCELLED:
                raise ForbiddenError("You can only cancel your own appointment.")
            if a.status not in (AppointmentStatus.BOOKED,
                                AppointmentStatus.CONFIRMED):
                raise BusinessRuleError("This appointment can no longer be cancelled.")
        else:
            if status == AppointmentStatus.CONFIRMED:
                if a.status != AppointmentStatus.BOOKED:
                    raise BusinessRuleError("Only booked appointments can be confirmed.")
                if a.appointment_date != date.today():
                    raise BusinessRuleError(
                        "Confirm on the day of the visit, when the patient arrives.")
                a.confirmed_at = datetime.now()
                a.confirmed_by_user_id = actor.id
            elif status in (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW):
                if a.status in (AppointmentStatus.COMPLETED,):
                    raise BusinessRuleError("Completed appointments cannot change.")
            elif status == AppointmentStatus.COMPLETED:
                if a.status not in (AppointmentStatus.BOOKED,
                                    AppointmentStatus.CONFIRMED):
                    raise BusinessRuleError(
                        "Only booked/confirmed appointments can be completed.")
            else:
                raise BusinessRuleError("Unsupported status change.")

        a.status = status
        await self.db.commit()
        return appointment_to_dict(a)
