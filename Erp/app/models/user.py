from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (AttendanceStatus, Designation, PayrollMode,
                              PayrollStatus, Role, Sex)


def _enum(e, length: int = 40):
    return sa.Enum(e, native_enum=False, length=length,
                   values_callable=lambda x: [m.value for m in x])


class User(Base):
    """Login identity. Exactly one of staff/patient profile is attached."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(sa.String(50), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(sa.String(200))
    role: Mapped[Role] = mapped_column(_enum(Role), index=True)
    full_name: Mapped[str] = mapped_column(sa.String(120))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    staff: Mapped["Staff | None"] = relationship(back_populates="user", uselist=False)
    patient = relationship("Patient", back_populates="user", uselist=False,
                           foreign_keys="Patient.user_id")


class Staff(Base):
    """Employee master — doctors, nurses, clerks, interns, pharmacists…"""

    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"), unique=True)

    full_name: Mapped[str] = mapped_column(sa.String(120))
    sex: Mapped[Sex] = mapped_column(_enum(Sex))
    date_of_birth: Mapped[date]
    designation: Mapped[Designation] = mapped_column(_enum(Designation), index=True)
    qualification: Mapped[str] = mapped_column(sa.String(200), default="")
    department: Mapped[str] = mapped_column(sa.String(40), default="GENERAL")

    phone: Mapped[str] = mapped_column(sa.String(15))
    email: Mapped[str] = mapped_column(sa.String(120), default="")
    address: Mapped[str] = mapped_column(sa.Text, default="")

    # sensitive KYC — exposed only to super admins & the employee themself
    aadhar_number: Mapped[str] = mapped_column(sa.String(12), default="")
    pan_number: Mapped[str] = mapped_column(sa.String(10), default="")
    bank_account_number: Mapped[str] = mapped_column(sa.String(20), default="")
    bank_ifsc: Mapped[str] = mapped_column(sa.String(11), default="")
    bank_name: Mapped[str] = mapped_column(sa.String(80), default="")

    monthly_salary: Mapped[int] = mapped_column(default=0)  # ₹
    date_joined: Mapped[date]
    shift_start: Mapped[str] = mapped_column(sa.String(5), default="10:00")  # HH:MM
    shift_end: Mapped[str] = mapped_column(sa.String(5), default="18:00")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    user: Mapped[User] = relationship(back_populates="staff")
    attendance: Mapped[list["Attendance"]] = relationship(back_populates="staff")
    salary_payments: Mapped[list["SalaryPayment"]] = relationship(back_populates="staff")

    @property
    def age(self) -> int:
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (sa.UniqueConstraint("staff_id", "day", name="uq_attendance_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(sa.ForeignKey("staff.id"), index=True)
    day: Mapped[date] = mapped_column(index=True)
    check_in: Mapped[datetime | None]
    check_out: Mapped[datetime | None]
    hours_worked: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[AttendanceStatus] = mapped_column(
        _enum(AttendanceStatus), default=AttendanceStatus.PRESENT)
    note: Mapped[str] = mapped_column(sa.String(200), default="")

    staff: Mapped[Staff] = relationship(back_populates="attendance")


class SalaryPayment(Base):
    __tablename__ = "salary_payments"
    __table_args__ = (
        sa.UniqueConstraint("staff_id", "month", "year", name="uq_salary_month"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(sa.ForeignKey("staff.id"), index=True)
    month: Mapped[int]
    year: Mapped[int]
    amount: Mapped[int]  # ₹
    mode: Mapped[PayrollMode] = mapped_column(_enum(PayrollMode))
    status: Mapped[PayrollStatus] = mapped_column(
        _enum(PayrollStatus), default=PayrollStatus.PAID)
    reference: Mapped[str] = mapped_column(sa.String(40))
    paid_on: Mapped[datetime] = mapped_column(default=datetime.now)
    paid_by_user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"))

    staff: Mapped[Staff] = relationship(back_populates="salary_payments")
