from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.exceptions.handlers import register_exception_handlers
from app.routers import (appointments, auth, billing, dashboard, frontend,
                         patients, pharmacy, public, staff, wards)

settings = get_settings()

STATIC_DIR = Path(__file__).resolve().parent / "frontend" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if settings.SEED_ON_STARTUP:
        from app.utils.seeder import seed_if_empty
        async with SessionLocal() as db:
            await seed_if_empty(db)
    yield


app = FastAPI(
    title="Dr. Palaskar Hospital ERP",
    version="1.0.0",
    description="Hospital management system — orthopaedics, ophthalmology "
                "and physiotherapy · Vasai (W).",
    lifespan=lifespan,
    docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json",
)

register_exception_handlers(app)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    else:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; font-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    return response


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(auth.router)
app.include_router(public.router)
app.include_router(patients.router)
app.include_router(pharmacy.router)
app.include_router(wards.router)
app.include_router(appointments.router)
app.include_router(billing.router)
app.include_router(staff.router)
app.include_router(dashboard.router)
app.include_router(frontend.router)


@app.get("/api/health", tags=["meta"])
async def health():
    return {"status": "ok", "hospital": "Dr. Palaskar Hospital"}
