from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_admin, require_staff
from app.schemas.operations import (MedicineCreate, MedicineOut,
                                    MedicineUpdate, StockAdjustIn,
                                    StockTxnOut)
from app.services.pharmacy_service import PharmacyService

router = APIRouter(prefix="/api/pharmacy", tags=["pharmacy"])


def get_service(db: AsyncSession = Depends(get_db)) -> PharmacyService:
    return PharmacyService(db)


@router.get("/medicines", response_model=list[MedicineOut])
async def list_medicines(q: str = Query("", max_length=60),
                         low_only: bool = Query(False),
                         _: CurrentUser = Depends(require_staff),
                         svc: PharmacyService = Depends(get_service)):
    return await svc.list_medicines(q, low_only)


@router.post("/medicines", response_model=MedicineOut, status_code=201)
async def create_medicine(data: MedicineCreate,
                          _: CurrentUser = Depends(require_admin),
                          svc: PharmacyService = Depends(get_service)):
    return await svc.create_medicine(data)


@router.patch("/medicines/{medicine_id}", response_model=MedicineOut)
async def update_medicine(medicine_id: int, data: MedicineUpdate,
                          _: CurrentUser = Depends(require_admin),
                          svc: PharmacyService = Depends(get_service)):
    return await svc.update_medicine(medicine_id, data)


@router.post("/stock", response_model=MedicineOut)
async def adjust_stock(data: StockAdjustIn,
                       actor: CurrentUser = Depends(require_staff),
                       svc: PharmacyService = Depends(get_service)):
    return await svc.adjust_stock(data, actor)


@router.get("/stock/history", response_model=list[StockTxnOut])
async def stock_history(medicine_id: int | None = Query(None),
                        _: CurrentUser = Depends(require_staff),
                        svc: PharmacyService = Depends(get_service)):
    return await svc.stock_history(medicine_id)


@router.get("/prescriptions/pending")
async def pending_prescriptions(_: CurrentUser = Depends(require_staff),
                                svc: PharmacyService = Depends(get_service)):
    return await svc.pending_prescriptions()


@router.post("/prescriptions/{prescription_id}/dispense")
async def dispense(prescription_id: int,
                   actor: CurrentUser = Depends(require_staff),
                   svc: PharmacyService = Depends(get_service)):
    return await svc.dispense_prescription(prescription_id, actor)
