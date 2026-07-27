from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app.utils.catalog import public_info

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "frontend" / "templates"
STATIC_DIR = Path(__file__).resolve().parents[1] / "frontend" / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter(tags=["frontend"], include_in_schema=False)


def _page(request: Request, name: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request, name, {"info": public_info()})


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return _page(request, "index.html")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return _page(request, "login.html")


@router.get("/portal", response_class=HTMLResponse)
async def portal(request: Request):
    return _page(request, "portal.html")


@router.get("/staff", response_class=HTMLResponse)
async def staff_app(request: Request):
    return _page(request, "staff.html")


@router.get("/admin", response_class=HTMLResponse)
async def admin_app(request: Request):
    return _page(request, "admin.html")


@router.get("/favicon.ico")
async def favicon():
    return FileResponse(STATIC_DIR / "img" / "favicon.png",
                        media_type="image/png")
