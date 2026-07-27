from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_admin, require_staff
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def get_service(db: AsyncSession = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


@router.get("/daily-report")
async def daily_report(day: date | None = Query(None),
                       _: CurrentUser = Depends(require_admin),
                       svc: DashboardService = Depends(get_service)):
    return await svc.daily_report(day)


@router.get("/charts")
async def charts(days: int = Query(30, ge=7, le=180),
                 _: CurrentUser = Depends(require_admin),
                 svc: DashboardService = Depends(get_service)):
    return await svc.charts(days)


@router.get("/staff-home")
async def staff_home(actor: CurrentUser = Depends(require_staff),
                     svc: DashboardService = Depends(get_service)):
    return await svc.staff_home(actor)

@router.get("/activity")
async def activity(limit: int = Query(30, ge=5, le=100),
                   _: CurrentUser = Depends(require_admin),
                   svc: DashboardService = Depends(get_service)):
    return await svc.activity(limit)
