from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_admin, require_any, require_staff
from app.models.enums import BillStatus, ReminderStatus
from app.schemas.operations import (BillOut, MediclaimOut, MediclaimUpdate,
                                    PayBillIn, ReminderCreate, ReminderOut)
from app.services.billing_service import BillingService

router = APIRouter(prefix="/api", tags=["billing"])


def get_service(db: AsyncSession = Depends(get_db)) -> BillingService:
    return BillingService(db)


# --------------------------------------------------------------------- bills
@router.get("/bills", response_model=list[BillOut])
async def list_bills(patient_id: int | None = Query(None),
                     status: BillStatus | None = Query(None),
                     actor: CurrentUser = Depends(require_any),
                     svc: BillingService = Depends(get_service)):
    return await svc.list_bills(actor, patient_id, status)


@router.get("/bills/{bill_id}", response_model=BillOut)
async def get_bill(bill_id: int, actor: CurrentUser = Depends(require_any),
                   svc: BillingService = Depends(get_service)):
    return await svc.get_bill(bill_id, actor)


@router.post("/bills/{bill_id}/pay", response_model=BillOut)
async def pay_bill(bill_id: int, data: PayBillIn,
                   actor: CurrentUser = Depends(require_any),
                   svc: BillingService = Depends(get_service)):
    return await svc.pay_bill(bill_id, data, actor)


# ----------------------------------------------------------------- reminders
@router.get("/reminders", response_model=list[ReminderOut])
async def list_reminders(status: ReminderStatus | None = Query(None),
                         _: CurrentUser = Depends(require_staff),
                         svc: BillingService = Depends(get_service)):
    return await svc.list_reminders(status)


@router.post("/reminders", status_code=201)
async def create_reminder(data: ReminderCreate,
                          actor: CurrentUser = Depends(require_staff),
                          svc: BillingService = Depends(get_service)):
    rem = await svc.create_reminder(data, actor)
    return {"id": rem.id, "ok": True}


@router.patch("/reminders/{reminder_id}/done")
async def mark_done(reminder_id: int,
                    _: CurrentUser = Depends(require_staff),
                    svc: BillingService = Depends(get_service)):
    rem = await svc.mark_reminder_done(reminder_id)
    return {"id": rem.id, "status": rem.status.value}


# ---------------------------------------------------------------- mediclaims
@router.get("/mediclaims", response_model=list[MediclaimOut])
async def list_claims(patient_id: int | None = Query(None),
                      actor: CurrentUser = Depends(require_any),
                      svc: BillingService = Depends(get_service)):
    return await svc.list_claims(actor, patient_id)


@router.patch("/mediclaims/{claim_id}", response_model=MediclaimOut)
async def update_claim(claim_id: int, data: MediclaimUpdate,
                       _: CurrentUser = Depends(require_admin),
                       svc: BillingService = Depends(get_service)):
    return await svc.update_claim(claim_id, data)
