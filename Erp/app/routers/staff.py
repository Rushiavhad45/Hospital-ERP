from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_admin, require_staff
from app.schemas.staff import (AttendanceMarkIn, AttendanceOut, AutopayIn,
                               PayrollPayIn, SalaryPaymentOut, StaffCreate,
                               StaffOut, StaffUpdate)
from app.services.staff_service import StaffService

router = APIRouter(prefix="/api/staff", tags=["staff"])


def get_service(db: AsyncSession = Depends(get_db)) -> StaffService:
    return StaffService(db)


def _att(a) -> dict:
    return {"id": a.id, "staff_id": a.staff_id, "day": a.day.isoformat(),
            "check_in": a.check_in.isoformat() if a.check_in else None,
            "check_out": a.check_out.isoformat() if a.check_out else None,
            "hours_worked": a.hours_worked, "status": a.status.value,
            "note": a.note}


# ----------------------------------------------------------------- employees
@router.get("", response_model=list[StaffOut])
async def list_staff(actor: CurrentUser = Depends(require_staff),
                     svc: StaffService = Depends(get_service)):
    return await svc.list_staff(actor)


@router.post("", response_model=StaffOut, status_code=201)
async def create_staff(data: StaffCreate,
                       actor: CurrentUser = Depends(require_admin),
                       svc: StaffService = Depends(get_service)):
    return await svc.create_staff(data, actor)


@router.get("/doctors")
async def doctors(_: CurrentUser = Depends(require_staff),
                  svc: StaffService = Depends(get_service)):
    return await svc.list_doctors()


@router.get("/nurses")
async def nurses(_: CurrentUser = Depends(require_staff),
                 svc: StaffService = Depends(get_service)):
    return await svc.list_nurses()


# ---------------------------------------------------------------- attendance
@router.post("/attendance/check-in", response_model=AttendanceOut)
async def check_in(actor: CurrentUser = Depends(require_staff),
                   svc: StaffService = Depends(get_service)):
    return _att(await svc.check_in(actor))


@router.post("/attendance/check-out", response_model=AttendanceOut)
async def check_out(actor: CurrentUser = Depends(require_staff),
                    svc: StaffService = Depends(get_service)):
    return _att(await svc.check_out(actor))


@router.get("/attendance/today")
async def today(actor: CurrentUser = Depends(require_staff),
                svc: StaffService = Depends(get_service)):
    rec = await svc.today_attendance(actor)
    return _att(rec) if rec else None


@router.get("/attendance/day-sheet")
async def day_sheet(day: date = Query(default_factory=date.today),
                    _: CurrentUser = Depends(require_admin),
                    svc: StaffService = Depends(get_service)):
    return await svc.day_sheet(day)


@router.post("/attendance/mark", response_model=AttendanceOut)
async def mark(data: AttendanceMarkIn,
               _: CurrentUser = Depends(require_admin),
               svc: StaffService = Depends(get_service)):
    return _att(await svc.mark_attendance(data))


@router.get("/{staff_id}/attendance/heatmap")
async def heatmap(staff_id: int, days: int = Query(182, ge=30, le=366),
                  actor: CurrentUser = Depends(require_staff),
                  svc: StaffService = Depends(get_service)):
    return await svc.heatmap(staff_id, actor, days)


# ------------------------------------------------------------------- payroll
@router.get("/payroll/preview")
async def payroll_preview(month: int = Query(..., ge=1, le=12),
                          year: int = Query(..., ge=2014, le=2100),
                          _: CurrentUser = Depends(require_admin),
                          svc: StaffService = Depends(get_service)):
    return await svc.payroll_preview(month, year)


@router.post("/payroll/pay", response_model=SalaryPaymentOut)
async def pay(data: PayrollPayIn,
              actor: CurrentUser = Depends(require_admin),
              svc: StaffService = Depends(get_service)):
    p = await svc.pay_salary(data, actor)
    return {"id": p.id, "staff_id": p.staff_id, "staff_name": "",
            "month": p.month, "year": p.year, "amount": p.amount,
            "mode": p.mode.value, "reference": p.reference,
            "paid_on": p.paid_on.isoformat()}


@router.post("/payroll/autopay")
async def autopay(data: AutopayIn,
                  actor: CurrentUser = Depends(require_admin),
                  svc: StaffService = Depends(get_service)):
    return await svc.autopay(data.month, data.year, actor)


@router.get("/payroll/history", response_model=list[SalaryPaymentOut])
async def payroll_history(staff_id: int | None = Query(None),
                          _: CurrentUser = Depends(require_admin),
                          svc: StaffService = Depends(get_service)):
    return await svc.payroll_history(staff_id)


# --- keep this LAST so it doesn't shadow /doctors, /payroll/... -------------
@router.get("/{staff_id}", response_model=StaffOut)
async def get_staff(staff_id: int,
                    actor: CurrentUser = Depends(require_staff),
                    svc: StaffService = Depends(get_service)):
    return await svc.get_staff(staff_id, actor)


@router.patch("/{staff_id}", response_model=StaffOut)
async def update_staff(staff_id: int, data: StaffUpdate,
                       _: CurrentUser = Depends(require_admin),
                       svc: StaffService = Depends(get_service)):
    return await svc.update_staff(staff_id, data)
