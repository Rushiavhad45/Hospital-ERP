from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.core.security import hash_password, validate_password_strength
from app.exceptions import (BusinessRuleError, ConflictError, ForbiddenError,
                            NotFoundError)
from app.models import Attendance, SalaryPayment, Staff
from app.models.enums import AttendanceStatus, PayrollMode, Role
from app.repositories.users import (AttendanceRepository, PayrollRepository,
                                    StaffRepository, UserRepository, make_user)
from app.schemas.staff import (AttendanceMarkIn, PayrollPayIn, StaffCreate,
                               StaffUpdate)
from app.utils.ids import payment_reference

SENSITIVE_FIELDS = ("aadhar_number", "pan_number", "bank_account_number",
                    "bank_ifsc", "bank_name", "monthly_salary")


def staff_to_dict(s: Staff, username: str | None = None, *, redact: bool) -> dict:
    d = {
        "id": s.id, "user_id": s.user_id, "username": username,
        "full_name": s.full_name, "sex": s.sex.value,
        "date_of_birth": s.date_of_birth.isoformat(), "age": s.age,
        "designation": s.designation.value, "qualification": s.qualification,
        "department": s.department, "phone": s.phone, "email": s.email,
        "address": s.address, "date_joined": s.date_joined.isoformat(),
        "shift_start": s.shift_start, "shift_end": s.shift_end,
        "is_active": s.is_active,
        "aadhar_number": s.aadhar_number, "pan_number": s.pan_number,
        "bank_account_number": s.bank_account_number, "bank_ifsc": s.bank_ifsc,
        "bank_name": s.bank_name, "monthly_salary": s.monthly_salary,
    }
    if redact:
        for f in SENSITIVE_FIELDS:
            d[f] = None
    return d


class StaffService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.staff = StaffRepository(db)
        self.users = UserRepository(db)
        self.attendance = AttendanceRepository(db)
        self.payroll = PayrollRepository(db)

    # ------------------------------------------------------------- employees
    async def create_staff(self, data: StaffCreate, actor: CurrentUser) -> dict:
        if await self.users.by_username(data.username):
            raise ConflictError(f"Username '{data.username}' is already taken.")
        validate_password_strength(data.password)
        role = Role.SUPER_ADMIN if data.username in ("sameer", "lalan") else Role.STAFF
        user = await self.users.add(make_user(
            data.username, hash_password(data.password), role, data.full_name))
        staff = await self.staff.add(Staff(
            user_id=user.id,
            **data.model_dump(exclude={"username", "password"})))
        await self.db.commit()
        return staff_to_dict(staff, user.username, redact=False)

    async def list_staff(self, actor: CurrentUser) -> list[dict]:
        rows = await self.staff.list_with_username()
        redact = actor.role != Role.SUPER_ADMIN
        return [staff_to_dict(s, u, redact=redact) for s, u in rows]

    async def list_doctors(self) -> list[dict]:
        return [{"id": s.id, "full_name": s.full_name, "department": s.department,
                 "qualification": s.qualification, "username": u,
                 "shift_start": s.shift_start, "shift_end": s.shift_end}
                for s, u in await self.staff.doctors()]

    async def list_nurses(self) -> list[dict]:
        rows = await self.staff.list_with_username(active_only=True)
        return [{"id": s.id, "full_name": s.full_name,
                 "designation": s.designation.value}
                for s, _ in rows if s.designation.value in ("NURSE", "INTERN")]

    async def get_staff(self, staff_id: int, actor: CurrentUser) -> dict:
        s = await self.staff.get(staff_id)
        if s is None:
            raise NotFoundError("Staff member not found.")
        is_self = actor.staff_id == s.id
        if actor.role != Role.SUPER_ADMIN and not is_self:
            raise ForbiddenError("You can only view your own employee profile.")
        user = await self.users.get(s.user_id)
        payments = await self.payroll.history(s.id)
        d = staff_to_dict(s, user.username if user else None, redact=False)
        d["salary_history"] = [
            {"id": p.id, "month": p.month, "year": p.year, "amount": p.amount,
             "mode": p.mode.value, "reference": p.reference,
             "paid_on": p.paid_on.isoformat()} for p, _ in payments]
        return d

    async def update_staff(self, staff_id: int, data: StaffUpdate) -> dict:
        s = await self.staff.get(staff_id)
        if s is None:
            raise NotFoundError("Staff member not found.")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(s, field, value)
        if data.is_active is not None:
            user = await self.users.get(s.user_id)
            if user:
                user.is_active = data.is_active
        if data.full_name:
            user = await self.users.get(s.user_id)
            if user:
                user.full_name = data.full_name
        await self.db.commit()
        user = await self.users.get(s.user_id)
        return staff_to_dict(s, user.username if user else None, redact=False)

    # ------------------------------------------------------------ attendance
    async def check_in(self, actor: CurrentUser) -> Attendance:
        if actor.staff_id is None:
            raise ForbiddenError("Only staff can mark attendance.")
        today = date.today()
        rec = await self.attendance.for_day(actor.staff_id, today)
        if rec and rec.check_in:
            raise ConflictError("You have already checked in today.")
        if rec is None:
            rec = await self.attendance.add(Attendance(
                staff_id=actor.staff_id, day=today,
                status=AttendanceStatus.PRESENT))
        rec.check_in = datetime.now()
        rec.status = AttendanceStatus.PRESENT
        await self.db.commit()
        return rec

    async def check_out(self, actor: CurrentUser) -> Attendance:
        if actor.staff_id is None:
            raise ForbiddenError("Only staff can mark attendance.")
        rec = await self.attendance.for_day(actor.staff_id, date.today())
        if rec is None or rec.check_in is None:
            raise BusinessRuleError("Check in first, then check out.")
        if rec.check_out:
            raise ConflictError("You have already checked out today.")
        rec.check_out = datetime.now()
        rec.hours_worked = round(
            (rec.check_out - rec.check_in).total_seconds() / 3600, 2)
        if rec.hours_worked < 4:
            rec.status = AttendanceStatus.HALF_DAY
        await self.db.commit()
        return rec

    async def today_attendance(self, actor: CurrentUser) -> Attendance | None:
        if actor.staff_id is None:
            return None
        return await self.attendance.for_day(actor.staff_id, date.today())

    async def mark_attendance(self, data: AttendanceMarkIn) -> Attendance:
        """Super-admin correction: mark ABSENT / LEAVE / WEEK_OFF etc."""
        if await self.staff.get(data.staff_id) is None:
            raise NotFoundError("Staff member not found.")
        rec = await self.attendance.for_day(data.staff_id, data.day)
        if rec is None:
            rec = await self.attendance.add(Attendance(
                staff_id=data.staff_id, day=data.day, status=data.status,
                note=data.note))
        else:
            rec.status, rec.note = data.status, data.note
        await self.db.commit()
        return rec

    async def heatmap(self, staff_id: int, actor: CurrentUser,
                      days: int = 182) -> list[dict]:
        if actor.role != Role.SUPER_ADMIN and actor.staff_id != staff_id:
            raise ForbiddenError("You can only view your own attendance.")
        from datetime import timedelta
        end = date.today()
        start = end - timedelta(days=days - 1)
        recs = await self.attendance.range_for_staff(staff_id, start, end)
        return [{"day": r.day.isoformat(), "hours": r.hours_worked,
                 "status": r.status.value,
                 "check_in": r.check_in.isoformat() if r.check_in else None,
                 "check_out": r.check_out.isoformat() if r.check_out else None}
                for r in recs]

    async def day_sheet(self, day: date) -> list[dict]:
        rows = await self.attendance.all_for_day(day)
        return [{"id": a.id, "staff_id": a.staff_id, "staff_name": name,
                 "day": a.day.isoformat(),
                 "check_in": a.check_in.isoformat() if a.check_in else None,
                 "check_out": a.check_out.isoformat() if a.check_out else None,
                 "hours_worked": a.hours_worked, "status": a.status.value,
                 "note": a.note} for a, name in rows]

    # --------------------------------------------------------------- payroll
    async def payroll_preview(self, month: int, year: int) -> list[dict]:
        rows = await self.staff.list_with_username(active_only=True)
        out = []
        for s, _u in rows:
            paid = await self.payroll.for_month(s.id, month, year)
            days = await self.attendance.month_days_present(s.id, month, year)
            out.append({"staff_id": s.id, "full_name": s.full_name,
                        "designation": s.designation.value,
                        "monthly_salary": s.monthly_salary,
                        "days_present": days,
                        "paid": paid is not None,
                        "reference": paid.reference if paid else None,
                        "paid_on": paid.paid_on.isoformat() if paid else None})
        return out

    async def pay_salary(self, data: PayrollPayIn, actor: CurrentUser) -> SalaryPayment:
        s = await self.staff.get(data.staff_id)
        if s is None:
            raise NotFoundError("Staff member not found.")
        if await self.payroll.for_month(s.id, data.month, data.year):
            raise ConflictError(
                f"{s.full_name} has already been paid for {data.month:02d}/{data.year}.")
        amount = data.amount_override if data.amount_override is not None else s.monthly_salary
        payment = await self.payroll.add(SalaryPayment(
            staff_id=s.id, month=data.month, year=data.year, amount=amount,
            mode=data.mode, reference=payment_reference(),
            paid_by_user_id=actor.id))
        await self.db.commit()
        return payment

    async def autopay(self, month: int, year: int, actor: CurrentUser) -> dict:
        rows = await self.staff.list_with_username(active_only=True)
        paid, skipped = [], []
        for s, _ in rows:
            if await self.payroll.for_month(s.id, month, year):
                skipped.append(s.full_name)
                continue
            await self.payroll.add(SalaryPayment(
                staff_id=s.id, month=month, year=year, amount=s.monthly_salary,
                mode=PayrollMode.AUTOPAY, reference=payment_reference(),
                paid_by_user_id=actor.id))
            paid.append(s.full_name)
        await self.db.commit()
        return {"paid": paid, "skipped_already_paid": skipped,
                "total_paid": len(paid)}

    async def payroll_history(self, staff_id: int | None = None) -> list[dict]:
        rows = await self.payroll.history(staff_id)
        return [{"id": p.id, "staff_id": p.staff_id, "staff_name": name,
                 "month": p.month, "year": p.year, "amount": p.amount,
                 "mode": p.mode.value, "reference": p.reference,
                 "paid_on": p.paid_on.isoformat()} for p, name in rows]
