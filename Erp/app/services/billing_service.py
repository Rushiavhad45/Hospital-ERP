from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.exceptions import (BusinessRuleError, ConflictError, ForbiddenError,
                            NotFoundError)
from app.models import Bill, Mediclaim, Reminder
from app.models.enums import BillStatus, ClaimStatus, ReminderStatus, Role
from app.repositories.billing import (BillRepository, MediclaimRepository,
                                      ReminderRepository)
from app.schemas.operations import (MediclaimUpdate, PayBillIn,
                                    ReminderCreate)
from app.utils.ids import txn_reference


def bill_to_dict(b: Bill) -> dict:
    return {"id": b.id, "bill_number": b.bill_number,
            "bill_type": b.bill_type.value, "patient_id": b.patient_id,
            "patient_name": b.patient.full_name if b.patient else "",
            "patient_code": b.patient.patient_code if b.patient else "",
            "consultation_id": b.consultation_id, "admission_id": b.admission_id,
            "subtotal": b.subtotal, "discount": b.discount, "total": b.total,
            "status": b.status.value,
            "payment_mode": b.payment_mode.value if b.payment_mode else None,
            "transaction_ref": b.transaction_ref,
            "generated_at": b.generated_at.isoformat(),
            "paid_at": b.paid_at.isoformat() if b.paid_at else None,
            "notes": b.notes,
            "items": [{"id": i.id, "category": i.category.value,
                       "description": i.description, "quantity": i.quantity,
                       "unit_price": i.unit_price, "amount": i.amount}
                      for i in b.items]}


class BillingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.bills = BillRepository(db)
        self.reminders = ReminderRepository(db)
        self.claims = MediclaimRepository(db)

    # ----------------------------------------------------------------- bills
    async def list_bills(self, actor: CurrentUser,
                         patient_id: int | None = None,
                         status: BillStatus | None = None) -> list[dict]:
        if actor.role == Role.PATIENT:
            patient_id = actor.patient_id
        return [bill_to_dict(b)
                for b in await self.bills.list_bills(patient_id, status)]

    async def get_bill(self, bill_id: int, actor: CurrentUser) -> dict:
        b = await self.bills.get_full(bill_id)
        if b is None:
            raise NotFoundError("Bill not found.")
        if actor.role == Role.PATIENT and b.patient_id != actor.patient_id:
            raise ForbiddenError("You can only view your own bills.")
        return bill_to_dict(b)

    async def pay_bill(self, bill_id: int, data: PayBillIn,
                       actor: CurrentUser) -> dict:
        """DEMO payment — no gateway is contacted. Marks the bill as PAID with
        a generated transaction reference."""
        b = await self.bills.get_full(bill_id)
        if b is None:
            raise NotFoundError("Bill not found.")
        if actor.role == Role.PATIENT and b.patient_id != actor.patient_id:
            raise ForbiddenError("You can only pay your own bills.")
        if b.status == BillStatus.PAID:
            raise ConflictError("This bill is already settled.")
        if b.status == BillStatus.CANCELLED:
            raise BusinessRuleError("This bill was cancelled.")
        b.status = BillStatus.PAID
        b.payment_mode = data.mode
        b.transaction_ref = txn_reference()
        b.paid_at = datetime.now()
        await self.db.commit()
        return bill_to_dict(b)

    # ------------------------------------------------------------- reminders
    async def create_reminder(self, data: ReminderCreate,
                              actor: CurrentUser) -> Reminder:
        rem = await self.reminders.add(Reminder(
            title=data.title, message=data.message, category=data.category,
            patient_id=data.patient_id, due_at=data.due_at,
            created_by_user_id=actor.id))
        await self.db.commit()
        return rem

    async def list_reminders(self, status: ReminderStatus | None) -> list[dict]:
        rows = await self.reminders.list_reminders(status)
        return [{"id": r.id, "title": r.title, "message": r.message,
                 "category": r.category.value, "patient_id": r.patient_id,
                 "patient_name": pname, "admission_id": r.admission_id,
                 "due_at": r.due_at.isoformat(), "status": r.status.value,
                 "created_at": r.created_at.isoformat()}
                for r, pname in rows]

    async def mark_reminder_done(self, reminder_id: int) -> Reminder:
        rem = await self.reminders.get(reminder_id)
        if rem is None:
            raise NotFoundError("Reminder not found.")
        if rem.status == ReminderStatus.DONE:
            raise ConflictError("Already marked done.")
        rem.status = ReminderStatus.DONE
        rem.done_at = datetime.now()
        await self.db.commit()
        return rem

    # ------------------------------------------------------------ mediclaims
    def _claim_to_dict(self, c: Mediclaim, name: str = "", code: str = "") -> dict:
        return {"id": c.id, "claim_number": c.claim_number,
                "admission_id": c.admission_id, "patient_id": c.patient_id,
                "patient_name": name, "patient_code": code,
                "insurer_name": c.insurer_name, "policy_number": c.policy_number,
                "tpa_name": c.tpa_name, "status": c.status.value,
                "summary": json.loads(c.summary_json or "{}"),
                "created_at": c.created_at.isoformat(),
                "finalized_at": c.finalized_at.isoformat()
                if c.finalized_at else None}

    async def list_claims(self, actor: CurrentUser,
                          patient_id: int | None = None) -> list[dict]:
        if actor.role == Role.PATIENT:
            patient_id = actor.patient_id
        rows = await self.claims.list_claims(patient_id)
        return [self._claim_to_dict(c, n, p) for c, n, p in rows]

    async def update_claim(self, claim_id: int, data: MediclaimUpdate) -> dict:
        c = await self.claims.get(claim_id)
        if c is None:
            raise NotFoundError("Mediclaim not found.")
        if data.status is not None:
            valid_next = {
                ClaimStatus.DRAFT: {ClaimStatus.DRAFT},
                ClaimStatus.FINALIZED: {ClaimStatus.SUBMITTED},
                ClaimStatus.SUBMITTED: {ClaimStatus.APPROVED,
                                        ClaimStatus.REJECTED},
                ClaimStatus.APPROVED: set(), ClaimStatus.REJECTED: set(),
            }
            if data.status != c.status and data.status not in valid_next[c.status]:
                raise BusinessRuleError(
                    f"A {c.status.value.lower()} claim cannot move to "
                    f"{data.status.value.lower()}.")
            c.status = data.status
        for field in ("insurer_name", "policy_number", "tpa_name"):
            value = getattr(data, field)
            if value is not None:
                setattr(c, field, value)
        await self.db.commit()
        return self._claim_to_dict(c)
