from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.core.security import (create_access_token, hash_password,
                               validate_password_strength, verify_password)
from app.exceptions import AuthError
from app.models import Patient, Staff, User
from app.models.enums import Role
from app.repositories.users import UserRepository
from app.utils.rate_limit import login_guard


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)

    async def login(self, username: str, password: str, client_ip: str) -> tuple[str, dict]:
        key = f"{username.lower()}|{client_ip}"
        login_guard.assert_not_locked(key)

        user = await self.users.by_username(username)
        if user is None or not verify_password(password, user.hashed_password):
            login_guard.record_failure(key)
            raise AuthError("Incorrect username or password.")
        if not user.is_active:
            raise AuthError("This account has been deactivated. Contact the hospital.")

        login_guard.reset(key)
        token = create_access_token(user_id=user.id, role=user.role.value,
                                    name=user.full_name)
        return token, await self.me_payload(user)

    async def me_payload(self, user: User) -> dict:
        out = {"id": user.id, "username": user.username, "role": user.role.value,
               "full_name": user.full_name, "staff_id": None, "patient_id": None,
               "designation": None}
        if user.role in (Role.SUPER_ADMIN, Role.STAFF):
            row = (await self.db.execute(
                select(Staff.id, Staff.designation).where(Staff.user_id == user.id)
            )).one_or_none()
            if row:
                out["staff_id"], out["designation"] = row[0], row[1].value
        elif user.role == Role.PATIENT:
            out["patient_id"] = (await self.db.execute(
                select(Patient.id).where(Patient.user_id == user.id)
            )).scalar_one_or_none()
        return out

    async def me(self, current: CurrentUser) -> dict:
        user = await self.users.get(current.id)
        if user is None:
            raise AuthError("Account not found.")
        return await self.me_payload(user)

    async def change_password(self, current: CurrentUser,
                              current_password: str, new_password: str) -> None:
        user = await self.users.get(current.id)
        if user is None or not verify_password(current_password, user.hashed_password):
            raise AuthError("Your current password is incorrect.")
        validate_password_strength(new_password)
        user.hashed_password = hash_password(new_password)
        await self.db.commit()
