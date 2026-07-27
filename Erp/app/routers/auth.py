from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import COOKIE_NAME, CurrentUser, get_current_user
from app.schemas.staff import ChangePasswordIn, LoginIn, MeOut, TokenOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def get_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, request: Request, response: Response,
                svc: AuthService = Depends(get_service)):
    ip = request.client.host if request.client else "?"
    token, me = await svc.login(data.username, data.password, ip)
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, samesite="strict",
        secure=settings.COOKIE_SECURE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/")
    return {"access_token": token, "token_type": "bearer", "user": me}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me", response_model=MeOut)
async def me(current: CurrentUser = Depends(get_current_user),
             svc: AuthService = Depends(get_service)):
    return await svc.me(current)


@router.post("/change-password")
async def change_password(data: ChangePasswordIn,
                          current: CurrentUser = Depends(get_current_user),
                          svc: AuthService = Depends(get_service)):
    await svc.change_password(current, data.current_password, data.new_password)
    return {"ok": True, "message": "Password updated."}
