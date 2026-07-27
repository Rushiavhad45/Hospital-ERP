"""FastAPI dependencies for authentication and role-based access control.

Token transport: ``Authorization: Bearer <jwt>`` header **or** the
``access_token`` HttpOnly cookie set at login (SameSite=Strict — the browser
never sends it cross-site, which is our CSRF story for this same-origin app).
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.exceptions import AuthError, ForbiddenError, NotFoundError
from app.models import Patient, Staff, User
from app.models.enums import Role

COOKIE_NAME = "access_token"


@dataclass
class CurrentUser:
    id: int
    username: str
    role: Role
    full_name: str
    staff_id: int | None = None
    patient_id: int | None = None
    designation: str | None = None


def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    cookie = request.cookies.get(COOKIE_NAME)
    if cookie:
        return cookie
    raise AuthError("Sign in to continue.")


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> CurrentUser:
    payload = decode_access_token(_extract_token(request))
    user = await db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthError("This account is disabled or no longer exists.")
    if user.role.value != payload.get("role"):
        raise AuthError("Session no longer valid — please sign in again.")

    cu = CurrentUser(id=user.id, username=user.username, role=user.role,
                     full_name=user.full_name)
    if user.role in (Role.SUPER_ADMIN, Role.STAFF):
        staff_id, designation = (
            await db.execute(select(Staff.id, Staff.designation)
                             .where(Staff.user_id == user.id))
        ).one_or_none() or (None, None)
        cu.staff_id = staff_id
        cu.designation = designation.value if designation else None
    elif user.role == Role.PATIENT:
        cu.patient_id = (
            await db.execute(select(Patient.id).where(Patient.user_id == user.id))
        ).scalar_one_or_none()
    return cu


def require_roles(*roles: Role):
    async def guard(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise ForbiddenError("You don't have permission for this action.")
        return user
    return guard


require_admin = require_roles(Role.SUPER_ADMIN)
require_staff = require_roles(Role.SUPER_ADMIN, Role.STAFF)   # any hospital employee
require_patient = require_roles(Role.PATIENT)
require_any = require_roles(Role.SUPER_ADMIN, Role.STAFF, Role.PATIENT)


async def get_current_patient(
    user: CurrentUser = Depends(require_patient),
) -> CurrentUser:
    if user.patient_id is None:
        raise NotFoundError("No patient profile is linked to this account.")
    return user
