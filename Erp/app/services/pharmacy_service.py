from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.exceptions import (BusinessRuleError, ConflictError,
                            InsufficientStockError, NotFoundError)
from app.models import Bill, BillItem, Medicine, StockTransaction
from app.models.enums import (BillItemCategory, BillStatus, BillType,
                              StockTxnType)
from app.repositories.billing import BillRepository
from app.repositories.facility import MedicineRepository
from app.repositories.patients import PrescriptionRepository
from app.schemas.operations import MedicineCreate, MedicineUpdate, StockAdjustIn
from app.utils.ids import bill_number


def medicine_to_dict(m: Medicine) -> dict:
    return {"id": m.id, "name": m.name, "generic_name": m.generic_name,
            "category": m.category, "manufacturer": m.manufacturer,
            "unit": m.unit, "unit_price": m.unit_price,
            "stock_quantity": m.stock_quantity, "reorder_level": m.reorder_level,
            "batch_number": m.batch_number,
            "expiry_date": m.expiry_date.isoformat() if m.expiry_date else None,
            "is_active": m.is_active, "low_stock": m.low_stock}


class PharmacyService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.medicines = MedicineRepository(db)
        self.prescriptions = PrescriptionRepository(db)
        self.bills = BillRepository(db)

    # ------------------------------------------------------------- catalogue
    async def create_medicine(self, data: MedicineCreate) -> dict:
        if await self.medicines.by_name(data.name):
            raise ConflictError(f"“{data.name}” is already in the catalogue.")
        med = await self.medicines.add(Medicine(**data.model_dump()))
        await self.db.commit()
        return medicine_to_dict(med)

    async def update_medicine(self, medicine_id: int, data: MedicineUpdate) -> dict:
        med = await self._get(medicine_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(med, field, value)
        await self.db.commit()
        return medicine_to_dict(med)

    async def _get(self, medicine_id: int) -> Medicine:
        med = await self.medicines.get(medicine_id)
        if med is None:
            raise NotFoundError("Medicine not found.")
        return med

    async def list_medicines(self, q: str = "", low_only: bool = False) -> list[dict]:
        return [medicine_to_dict(m)
                for m in await self.medicines.search(q, low_only)]

    # ----------------------------------------------------------------- stock
    async def _move_stock(self, med: Medicine, txn_type: StockTxnType,
                          quantity: int, reference: str, actor_id: int) -> None:
        """Adjust stock and write the audit row. Caller commits."""
        if txn_type == StockTxnType.OUT:
            if med.stock_quantity < quantity:
                raise InsufficientStockError(
                    f"Only {med.stock_quantity} × {med.name} in stock "
                    f"(needed {quantity}).",
                    details={"medicine_id": med.id,
                             "available": med.stock_quantity})
            med.stock_quantity -= quantity
        elif txn_type == StockTxnType.IN:
            med.stock_quantity += quantity
        else:  # ADJUSTMENT sets the absolute count
            med.stock_quantity = quantity
        self.db.add(StockTransaction(
            medicine_id=med.id, txn_type=txn_type, quantity=quantity,
            balance_after=med.stock_quantity, reference=reference,
            performed_by_user_id=actor_id))

    async def adjust_stock(self, data: StockAdjustIn, actor: CurrentUser) -> dict:
        med = await self._get(data.medicine_id)
        await self._move_stock(med, data.txn_type, data.quantity,
                               data.reference, actor.id)
        await self.db.commit()
        return medicine_to_dict(med)

    async def stock_history(self, medicine_id: int | None = None) -> list[dict]:
        rows = await self.medicines.transactions(medicine_id)
        return [{"id": t.id, "medicine_id": t.medicine_id, "medicine_name": name,
                 "txn_type": t.txn_type.value, "quantity": t.quantity,
                 "balance_after": t.balance_after, "reference": t.reference,
                 "created_at": t.created_at.isoformat()} for t, name in rows]

    # ------------------------------------------------------------ dispensing
    async def pending_prescriptions(self) -> list[dict]:
        rows = await self.prescriptions.pending_dispense()
        return [{"id": rx.id, "consultation_id": rx.consultation_id,
                 "patient_name": name, "patient_code": code,
                 "created_at": rx.created_at.isoformat(), "notes": rx.notes,
                 "items": [{"id": i.id, "medicine_id": i.medicine_id,
                            "medicine_name": i.medicine_name,
                            "quantity": i.quantity, "dosage": i.dosage}
                           for i in rx.items]}
                for rx, name, code in rows]

    async def dispense_prescription(self, prescription_id: int,
                                    actor: CurrentUser) -> dict:
        """Hand medicines over the counter: deduct stock for every catalogued
        item and append the charges to the consultation's OPD bill (or raise a
        fresh PHARMACY bill if that bill is already settled)."""
        rx = await self.prescriptions.get_full(prescription_id)
        if rx is None:
            raise NotFoundError("Prescription not found.")
        if rx.dispensed:
            raise ConflictError("This prescription has already been dispensed.")

        stocked = [i for i in rx.items if i.medicine_id and i.quantity > 0]
        if not stocked:
            rx.dispensed, rx.dispensed_at = True, datetime.now()
            await self.db.commit()
            return {"dispensed": True, "billed_items": 0, "bill_id": None}

        bill = await self.bills.for_consultation(rx.consultation_id)
        if bill is None or bill.status != BillStatus.PENDING:
            bill = await self.bills.add(Bill(
                bill_number=bill_number(), bill_type=BillType.PHARMACY,
                patient_id=rx.patient_id, consultation_id=rx.consultation_id))

        for item in stocked:
            med = await self._get(item.medicine_id)
            await self._move_stock(med, StockTxnType.OUT, item.quantity,
                                   f"Rx #{rx.id}", actor.id)
            amount = med.unit_price * item.quantity
            self.db.add(BillItem(
                bill_id=bill.id, category=BillItemCategory.MEDICINE,
                description=f"{med.name} ({med.unit})", quantity=item.quantity,
                unit_price=med.unit_price, amount=amount))
            bill.subtotal += amount
            bill.total = bill.subtotal - bill.discount

        rx.dispensed, rx.dispensed_at = True, datetime.now()
        await self.db.commit()
        return {"dispensed": True, "billed_items": len(stocked), "bill_id": bill.id}
