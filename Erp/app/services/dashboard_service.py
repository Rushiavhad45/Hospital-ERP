from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.models import (Admission, Appointment, Bill, Patient, Room, Staff,
                        Surgery)
from app.models.enums import (AdmissionStatus, AppointmentStatus, BillStatus,
                              RoomStatus, SurgeryStatus)
from app.repositories.billing import (AnalyticsRepository,
                                      AppointmentRepository, BillRepository,
                                      ReminderRepository)
from app.repositories.facility import (AdmissionRepository,
                                       MedicineRepository, RoomRepository,
                                       SurgeryRepository)
from app.repositories.patients import ConsultationRepository, PhysioRepository
from app.repositories.users import AttendanceRepository, StaffRepository


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.analytics = AnalyticsRepository(db)
        self.bills = BillRepository(db)
        self.consultations = ConsultationRepository(db)
        self.admissions = AdmissionRepository(db)
        self.rooms = RoomRepository(db)
        self.surgeries = SurgeryRepository(db)
        self.appointments = AppointmentRepository(db)
        self.medicines = MedicineRepository(db)
        self.attendance = AttendanceRepository(db)
        self.staff = StaffRepository(db)
        self.reminders = ReminderRepository(db)
        self.physio = PhysioRepository(db)

    async def _room_snapshot(self) -> dict:
        by_type: dict = {}
        occupied = total = 0
        for rt, status, count in await self.rooms.occupancy_by_type():
            rec = by_type.setdefault(rt.value, {"total": 0, "occupied": 0})
            rec["total"] += count
            total += count
            if status == RoomStatus.OCCUPIED:
                rec["occupied"] += count
                occupied += count
        return {"total": total, "occupied": occupied,
                "free": total - occupied, "by_type": by_type}

    async def daily_report(self, day: date | None = None) -> dict:
        """Everything that happened at the hospital today — the super-admin's
        evening read."""
        day = day or date.today()
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)

        consultations = await self.consultations.on_day(day)
        surgeries_today = await self.surgeries.on_day(day)
        appts = await self.appointments.list_between(day, day)

        attendance_rows = await self.attendance.all_for_day(day)
        present = sum(1 for a, _ in attendance_rows
                      if a.status.value in ("PRESENT", "HALF_DAY"))
        active_staff = len(await self.staff.list_with_username(active_only=True))

        active_admissions = await self.admissions.list_admissions(
            AdmissionStatus.ADMITTED)

        return {
            "date": day.isoformat(),
            "consultations": {
                "count": len(consultations),
                "revenue": sum(c.fee for c in consultations),
                "by_department": self._group(
                    consultations, key=lambda c: c.department.value),
                "list": [{"id": c.id, "patient": c.patient.full_name,
                          "doctor": c.doctor.full_name,
                          "department": c.department.value,
                          "diagnosis": c.diagnosis,
                          "time": c.visited_at.strftime("%H:%M")}
                         for c in consultations],
            },
            "patients": {
                "new_registrations": await self.analytics.new_patients_on(day),
                "admitted_today": await self.admissions.admitted_on(day),
                "discharged_today": await self.admissions.discharged_on(day),
                "currently_admitted": len(active_admissions),
            },
            "appointments": {
                "total": len(appts),
                "by_status": self._group(appts, key=lambda a: a.status.value),
            },
            "surgeries": {
                "count": len(surgeries_today),
                "list": [{"id": s.id, "name": s.name,
                          "patient": s.patient.full_name,
                          "surgeon": s.surgeon.full_name,
                          "theatre": s.theatre.name, "status": s.status.value}
                         for s in surgeries_today],
            },
            "physio_sessions": await self.physio.sessions_on(day),
            "rooms": await self._room_snapshot(),
            "revenue": {
                "collected_today": await self.bills.revenue_on(day),
                "pending_overall": await self.bills.pending_total(),
            },
            "staff_attendance": {"present": present, "total": active_staff},
            "low_stock": [
                {"id": m.id, "name": m.name, "stock": m.stock_quantity,
                 "reorder_level": m.reorder_level}
                for m in await self.medicines.search(low_only=True)],
        }

    @staticmethod
    def _group(items, key) -> dict:
        out: dict = {}
        for item in items:
            out[key(item)] = out.get(key(item), 0) + 1
        return out

    async def charts(self, days: int = 30) -> dict:
        """Series consumed by Chart.js on the admin dashboard."""
        days = max(7, min(days, 180))
        labels = [(date.today() - timedelta(days=d)).isoformat()
                  for d in range(days - 1, -1, -1)]
        revenue = dict(await self.bills.revenue_series(days))
        consults = dict(await self.analytics.consultations_series(days))
        return {
            "labels": labels,
            "revenue": [revenue.get(d, 0) for d in labels],
            "consultations": [consults.get(d, 0) for d in labels],
            "departments": [
                {"department": dep.value, "count": count}
                for dep, count in await self.analytics.department_split()],
            "top_medicines": [
                {"name": name, "quantity": int(qty or 0)}
                for name, qty in await self.analytics.top_medicines()],
            "occupancy": (await self._room_snapshot())["by_type"],
        }

    async def staff_home(self, actor: CurrentUser) -> dict:
        """Compact summary for the staff landing screen."""
        today = date.today()
        appts = await self.appointments.list_between(today, today)
        att = (await self.attendance.for_day(actor.staff_id, today)
               if actor.staff_id else None)
        pending = await self.reminders.list_reminders(None, limit=8)
        return {
            "today": today.isoformat(),
            "appointments_today": len(appts),
            "appointments_waiting": sum(
                1 for a in appts if a.status == AppointmentStatus.BOOKED),
            "admitted_now": len(await self.admissions.list_admissions(
                AdmissionStatus.ADMITTED)),
            "rooms": await self._room_snapshot(),
            "low_stock_count": len(await self.medicines.search(low_only=True)),
            "my_attendance": {
                "checked_in": att.check_in.isoformat() if att and att.check_in else None,
                "checked_out": att.check_out.isoformat() if att and att.check_out else None,
            },
            "reminders": [
                {"id": r.id, "title": r.title, "category": r.category.value,
                 "status": r.status.value, "due_at": r.due_at.isoformat()}
                for r, _ in pending][:8],
        }

    # ------------------------------------------------------------ activity
    async def activity(self, limit: int = 30) -> list[dict]:
        """A merged, reverse-chronological feed of notable events across the
        hospital — admissions, discharges, staff check-ins, payments,
        consultations, bookings, surgeries and new registrations."""
        from app.models import (Admission, Appointment, Attendance, Bill,
                                Consultation, Patient, Staff, Surgery)
        from app.models.enums import BillStatus

        events: list[dict] = []

        def add(at, icon, kind, text):
            if at:
                events.append({"at": at.isoformat(), "icon": icon,
                               "kind": kind, "text": text})

        adms = (await self.db.execute(
            select(Admission).options(
                selectinload(Admission.patient), selectinload(Admission.room),
                selectinload(Admission.primary_doctor))
            .order_by(Admission.admitted_at.desc()).limit(limit))).scalars()
        for a in adms:
            add(a.admitted_at, "🛏", "ADMISSION",
                f"{a.patient.full_name} admitted to {a.room.room_number} "
                f"under {a.primary_doctor.full_name}"
                + (" (emergency)" if a.admission_type.value == "EMERGENCY" else ""))
            add(a.discharged_at, "✅", "DISCHARGE",
                f"{a.patient.full_name} discharged from {a.room.room_number}")

        atts = (await self.db.execute(
            select(Attendance, Staff.full_name)
            .join(Staff, Staff.id == Attendance.staff_id)
            .where(Attendance.check_in.is_not(None))
            .order_by(Attendance.check_in.desc()).limit(limit))).all()
        for att, name in atts:
            add(att.check_in, "✋", "CHECK_IN", f"{name} checked in")
            add(att.check_out, "👋", "CHECK_OUT", f"{name} checked out")

        bills = (await self.db.execute(
            select(Bill).options(selectinload(Bill.patient))
            .where(Bill.status == BillStatus.PAID,
                   Bill.paid_at.is_not(None))
            .order_by(Bill.paid_at.desc()).limit(limit))).scalars()
        for b in bills:
            add(b.paid_at, "💰", "PAYMENT",
                f"₹{b.total:,} received from {b.patient.full_name} "
                f"({b.bill_type.value} · {b.bill_number})")

        cons = (await self.db.execute(
            select(Consultation).options(
                selectinload(Consultation.patient),
                selectinload(Consultation.doctor))
            .order_by(Consultation.visited_at.desc()).limit(limit))).scalars()
        for c in cons:
            add(c.visited_at, "🩺", "CONSULTATION",
                f"{c.doctor.full_name} saw {c.patient.full_name}"
                + (f" — {c.diagnosis}" if c.diagnosis else ""))

        appts = (await self.db.execute(
            select(Appointment).options(
                selectinload(Appointment.doctor),
                selectinload(Appointment.patient))
            .order_by(Appointment.created_at.desc()).limit(limit))).scalars()
        for ap in appts:
            who = ap.patient.full_name if ap.patient else (ap.guest_name or "Guest")
            add(ap.created_at, "📅", "BOOKING",
                f"{who} booked {ap.slot} on {ap.appointment_date:%d %b} "
                f"with {ap.doctor.full_name} "
                f"({ap.booked_via.value.lower().replace('_', ' ')})")

        sx = (await self.db.execute(
            select(Surgery).options(selectinload(Surgery.patient))
            .order_by(Surgery.scheduled_at.desc()).limit(limit))).scalars()
        for s in sx:
            add(s.started_at, "🔪", "SURGERY",
                f"Surgery started: {s.name} — {s.patient.full_name}")
            add(s.ended_at, "🧵", "SURGERY",
                f"Surgery completed: {s.name} — {s.patient.full_name}")

        pats = (await self.db.execute(
            select(Patient).order_by(Patient.created_at.desc())
            .limit(limit))).scalars()
        for pt in pats:
            add(pt.created_at, "🆕", "REGISTRATION",
                f"{pt.full_name} registered ({pt.patient_code})")

        events.sort(key=lambda e: e["at"], reverse=True)
        return events[:limit]
