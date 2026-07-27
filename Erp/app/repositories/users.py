from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy import func, select

from app.models import Attendance, SalaryPayment, Staff, User
from app.models.enums import Designation, Role
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def by_username(self, username: str) -> User | None:
        return (await self.db.execute(
            select(User).where(func.lower(User.username) == username.lower())
        )).scalar_one_or_none()


class StaffRepository(BaseRepository[Staff]):
    model = Staff

    async def list_with_username(
        self, *, active_only: bool = False, designation: Designation | None = None
    ) -> Sequence[tuple[Staff, str]]:
        stmt = (select(Staff, User.username).join(User, Staff.user_id == User.id)
                .order_by(Staff.full_name))
        if active_only:
            stmt = stmt.where(Staff.is_active.is_(True))
        if designation:
            stmt = stmt.where(Staff.designation == designation)
        return (await self.db.execute(stmt)).all()

    async def doctors(self) -> Sequence[tuple[Staff, str]]:
        return await self.list_with_username(
            active_only=True, designation=Designation.DOCTOR)

    async def by_user_id(self, user_id: int) -> Staff | None:
        return (await self.db.execute(
            select(Staff).where(Staff.user_id == user_id))).scalar_one_or_none()

    async def by_username(self, username: str) -> Staff | None:
        return (await self.db.execute(
            select(Staff).join(User, Staff.user_id == User.id)
            .where(func.lower(User.username) == username.lower())
        )).scalar_one_or_none()


class AttendanceRepository(BaseRepository[Attendance]):
    model = Attendance

    async def for_day(self, staff_id: int, day: date) -> Attendance | None:
        return (await self.db.execute(
            select(Attendance).where(Attendance.staff_id == staff_id,
                                     Attendance.day == day)
        )).scalar_one_or_none()

    async def range_for_staff(
        self, staff_id: int, start: date, end: date
    ) -> Sequence[Attendance]:
        return (await self.db.execute(
            select(Attendance)
            .where(Attendance.staff_id == staff_id,
                   Attendance.day >= start, Attendance.day <= end)
            .order_by(Attendance.day)
        )).scalars().all()

    async def all_for_day(self, day: date) -> Sequence[tuple[Attendance, str]]:
        return (await self.db.execute(
            select(Attendance, Staff.full_name)
            .join(Staff, Attendance.staff_id == Staff.id)
            .where(Attendance.day == day).order_by(Staff.full_name)
        )).all()

    async def month_days_present(self, staff_id: int, month: int, year: int) -> int:
        return (await self.db.execute(
            select(func.count()).select_from(Attendance)
            .where(Attendance.staff_id == staff_id,
                   func.strftime("%m", Attendance.day) == f"{month:02d}",
                   func.strftime("%Y", Attendance.day) == str(year),
                   Attendance.status.in_(["PRESENT", "HALF_DAY"]))
        )).scalar_one()


class PayrollRepository(BaseRepository[SalaryPayment]):
    model = SalaryPayment

    async def for_month(self, staff_id: int, month: int, year: int) -> SalaryPayment | None:
        return (await self.db.execute(
            select(SalaryPayment).where(SalaryPayment.staff_id == staff_id,
                                        SalaryPayment.month == month,
                                        SalaryPayment.year == year)
        )).scalar_one_or_none()

    async def history(self, staff_id: int | None = None) -> Sequence[tuple[SalaryPayment, str]]:
        stmt = (select(SalaryPayment, Staff.full_name)
                .join(Staff, SalaryPayment.staff_id == Staff.id)
                .order_by(SalaryPayment.paid_on.desc()))
        if staff_id:
            stmt = stmt.where(SalaryPayment.staff_id == staff_id)
        return (await self.db.execute(stmt)).all()


def make_user(username: str, hashed_password: str, role: Role, full_name: str) -> User:
    return User(username=username.lower(), hashed_password=hashed_password,
                role=role, full_name=full_name)
