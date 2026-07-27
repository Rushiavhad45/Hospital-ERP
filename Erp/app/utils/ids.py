"""Human-readable reference number generators (collision-safe via random hex)."""
from __future__ import annotations

import secrets
from datetime import datetime


def _rand(n: int = 3) -> str:
    return secrets.token_hex(n).upper()


def patient_code(seq: int) -> str:
    return f"P{seq:05d}"


def appointment_code() -> str:
    return f"APT-{_rand(3)}"


def bill_number(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return f"B{now:%y%m}-{_rand(3)}"


def claim_number() -> str:
    return f"CLM-{_rand(4)}"


def payment_reference() -> str:
    return f"PAY-{_rand(4)}"


def txn_reference() -> str:
    return f"TXN-{_rand(5)}"
