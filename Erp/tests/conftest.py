"""Shared fixtures.

The environment MUST be configured before ``app`` is imported, because the
async engine binds to ``DATABASE_URL`` at import time.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

import httpx
import pytest

_TMP = Path(tempfile.mkdtemp(prefix="erp-test-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP / 'test.db'}"
os.environ["UPLOAD_DIR"] = str(_TMP / "uploads")
os.environ["SEED_ON_STARTUP"] = "0"
os.environ["RATE_LIMIT_ENABLED"] = "0"

from app.core.database import Base, SessionLocal, engine, init_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (Medicine, OperationTheatre, Patient, Room,  # noqa: E402
                        Staff, StockTransaction, User)
from app.models.enums import (Designation, OTCategory, Role, RoomType,  # noqa: E402
                              Sex, StockTxnType)

PW = "Testpass@1"


async def _mini_seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        pw = hash_password(PW)

        def user(uname, role, name):
            u = User(username=uname, hashed_password=pw, role=role,
                     full_name=name)
            db.add(u)
            return u

        u_sameer = user("sameer", Role.SUPER_ADMIN, "Dr. Sameer S. Palaskar")
        u_lalan = user("lalan", Role.SUPER_ADMIN, "Dr. Lalan S. Palaskar")
        u_nurse = user("nurse", Role.STAFF, "Anita R. Chaudhari")
        u_clerk = user("clerk", Role.STAFF, "Priya D. Shah")
        u_pat = user("pat1", Role.PATIENT, "Ramesh B. Sawant")
        u_pat2 = user("pat2", Role.PATIENT, "Sunita R. Mhatre")
        await db.flush()

        common = dict(sex=Sex.MALE, date_of_birth=date(1980, 1, 1),
                      phone="9000000000", monthly_salary=50000,
                      date_joined=date(2020, 1, 1), address="Vasai")
        db.add(Staff(user_id=u_sameer.id, full_name=u_sameer.full_name,
                     designation=Designation.DOCTOR, qualification="D.N.B",
                     department="ORTHOPAEDICS",
                     shift_start="00:00", shift_end="23:30",
                     aadhar_number="111122223333", pan_number="ABCDE1234F",
                     bank_account_number="9999", **common))
        db.add(Staff(user_id=u_lalan.id, full_name=u_lalan.full_name,
                     designation=Designation.DOCTOR, qualification="DOMS",
                     department="OPHTHALMOLOGY",
                     shift_start="00:00", shift_end="23:30",
                     **{**common, "sex": Sex.FEMALE, "phone": "9000000001"}))
        db.add(Staff(user_id=u_nurse.id, full_name=u_nurse.full_name,
                     designation=Designation.NURSE, qualification="GNM",
                     department="NURSING", shift_start="08:00",
                     shift_end="16:00",
                     **{**common, "sex": Sex.FEMALE, "phone": "9000000002"}))
        db.add(Staff(user_id=u_clerk.id, full_name=u_clerk.full_name,
                     designation=Designation.CLERK, qualification="B.Com",
                     department="FRONT OFFICE", shift_start="09:00",
                     shift_end="18:00",
                     **{**common, "sex": Sex.FEMALE, "phone": "9000000003"}))
        await db.flush()

        db.add(Patient(patient_code="P00001", user_id=u_pat.id,
                       full_name=u_pat.full_name, sex=Sex.MALE,
                       date_of_birth=date(1965, 5, 2), phone="9890011001",
                       created_by_user_id=u_sameer.id))
        db.add(Patient(patient_code="P00002", user_id=u_pat2.id,
                       full_name=u_pat2.full_name, sex=Sex.FEMALE,
                       date_of_birth=date(1972, 8, 19), phone="9890011002",
                       created_by_user_id=u_sameer.id))

        m1 = Medicine(name="Tab Diclofenac 50 mg", unit="strip", unit_price=100,
                      stock_quantity=50, reorder_level=10)
        m2 = Medicine(name="Inj Ceftriaxone 1 g", unit="vial", unit_price=250,
                      stock_quantity=3, reorder_level=5)
        db.add_all([m1, m2])
        await db.flush()
        for m in (m1, m2):
            db.add(StockTransaction(medicine_id=m.id, txn_type=StockTxnType.IN,
                                    quantity=m.stock_quantity,
                                    balance_after=m.stock_quantity,
                                    reference="Opening",
                                    performed_by_user_id=u_sameer.id))

        db.add(Room(room_number="E101", room_type=RoomType.ECONOMY,
                    daily_rate=1500, floor=1))
        db.add(Room(room_number="ICU-1", room_type=RoomType.ICU,
                    daily_rate=5000, floor=1))
        db.add(OperationTheatre(name="OT-1", category=OTCategory.MAJOR,
                                equipment="C-arm"))
        db.add(OperationTheatre(name="OT-2", category=OTCategory.MINOR,
                                equipment="Phaco"))
        await db.commit()


@pytest.fixture()
async def client():
    await init_db()
    await _mini_seed()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport,
                                 base_url="http://test") as c:
        yield c


async def _login(client: httpx.AsyncClient, username: str) -> dict:
    r = await client.post("/api/auth/login",
                          json={"username": username, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
async def admin_h(client):
    return await _login(client, "sameer")


@pytest.fixture()
async def lalan_h(client):
    return await _login(client, "lalan")


@pytest.fixture()
async def staff_h(client):
    return await _login(client, "nurse")


@pytest.fixture()
async def patient_h(client):
    return await _login(client, "pat1")


@pytest.fixture()
async def patient2_h(client):
    return await _login(client, "pat2")


def next_weekday() -> str:
    """Today if it isn't Sunday, else tomorrow (Monday)."""
    d = date.today()
    if d.weekday() == 6:
        d += timedelta(days=1)
    return d.isoformat()
