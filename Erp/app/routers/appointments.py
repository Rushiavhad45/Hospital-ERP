from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_patient, require_any
from app.schemas.operations import (AppointmentOut, AppointmentStatusIn,
                                    PortalAppointmentIn)
from app.services.appointment_service import AppointmentService

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


def get_service(db: AsyncSession = Depends(get_db)) -> AppointmentService:
    return AppointmentService(db)


@router.get("", response_model=list[AppointmentOut])
async def list_appointments(day: date | None = Query(None),
                            span_days: int = Query(1, ge=1, le=7),
                            actor: CurrentUser = Depends(require_any),
                            svc: AppointmentService = Depends(get_service)):
    return await svc.list_appointments(actor, day, span_days)


@router.post("", response_model=AppointmentOut, status_code=201)
async def book_portal(data: PortalAppointmentIn,
                      actor: CurrentUser = Depends(get_current_patient),
                      svc: AppointmentService = Depends(get_service)):
    return await svc.book_portal(data, actor)


@router.patch("/{appointment_id}/status", response_model=AppointmentOut)
async def set_status(appointment_id: int, data: AppointmentStatusIn,
                     actor: CurrentUser = Depends(require_any),
                     svc: AppointmentService = Depends(get_service)):
    return await svc.set_status(appointment_id, data.status, actor)
