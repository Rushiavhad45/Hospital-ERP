from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.operations import AppointmentOut, GuestAppointmentIn
from app.services.appointment_service import AppointmentService
from app.services.staff_service import StaffService
from app.utils.catalog import public_info
from app.utils.rate_limit import check_rate

router = APIRouter(prefix="/api/public", tags=["public"])


def get_appointments(db: AsyncSession = Depends(get_db)) -> AppointmentService:
    return AppointmentService(db)


def get_staff_svc(db: AsyncSession = Depends(get_db)) -> StaffService:
    return StaffService(db)


@router.get("/info")
async def info():
    """Hospital identity, treatments, facilities, physiotherapy catalogue."""
    return public_info()


@router.get("/doctors")
async def doctors(svc: StaffService = Depends(get_staff_svc)):
    return await svc.list_doctors()


@router.get("/slots")
async def slots(doctor_id: int = Query(..., ge=1),
                on: date = Query(...),
                svc: AppointmentService = Depends(get_appointments)):
    return await svc.available_slots(doctor_id, on)


@router.post("/appointments", response_model=AppointmentOut, status_code=201)
async def book_guest(data: GuestAppointmentIn, request: Request,
                     svc: AppointmentService = Depends(get_appointments)):
    ip = request.client.host if request.client else "?"
    check_rate(f"guest-book|{ip}", limit=5, per_seconds=3600)
    return await svc.book_guest(data)


@router.get("/appointments/track", response_model=AppointmentOut)
async def track(code: str = Query(..., min_length=4),
                phone: str = Query(..., min_length=10),
                request: Request = None,
                svc: AppointmentService = Depends(get_appointments)):
    ip = request.client.host if request and request.client else "?"
    check_rate(f"guest-track|{ip}", limit=30, per_seconds=3600)
    return await svc.track_guest(code, phone)
