from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_admin, require_staff
from app.models.enums import AdmissionStatus, SurgeryStatus
from app.schemas.operations import (AdmissionCreate, AdmissionOut,
                                    CareLogCreate, DischargeIn, RoomCreate,
                                    RoomOut, RoomUpdate, SurgeryCreate,
                                    SurgeryOut, SurgeryStatusIn, TheatreOut)
from app.services.ward_service import WardService

router = APIRouter(prefix="/api", tags=["wards"])


def get_service(db: AsyncSession = Depends(get_db)) -> WardService:
    return WardService(db)


# --------------------------------------------------------------------- rooms
@router.get("/rooms", response_model=list[RoomOut])
async def room_board(_: CurrentUser = Depends(require_staff),
                     svc: WardService = Depends(get_service)):
    return await svc.room_board()


@router.post("/rooms", response_model=RoomOut, status_code=201)
async def create_room(data: RoomCreate,
                      _: CurrentUser = Depends(require_admin),
                      svc: WardService = Depends(get_service)):
    room = await svc.create_room(data)
    return {"id": room.id, "room_number": room.room_number,
            "room_type": room.room_type.value, "daily_rate": room.daily_rate,
            "status": room.status.value, "floor": room.floor,
            "notes": room.notes, "admission_id": None,
            "occupant_patient_id": None, "occupant_name": None,
            "admitted_at": None, "doctor_name": None, "nurse_name": None}


@router.patch("/rooms/{room_id}", response_model=RoomOut)
async def update_room(room_id: int, data: RoomUpdate,
                      _: CurrentUser = Depends(require_admin),
                      svc: WardService = Depends(get_service)):
    room = await svc.update_room(room_id, data)
    return {"id": room.id, "room_number": room.room_number,
            "room_type": room.room_type.value, "daily_rate": room.daily_rate,
            "status": room.status.value, "floor": room.floor,
            "notes": room.notes, "admission_id": None,
            "occupant_patient_id": None, "occupant_name": None,
            "admitted_at": None, "doctor_name": None, "nurse_name": None}


# ---------------------------------------------------------------- admissions
@router.post("/admissions", response_model=AdmissionOut, status_code=201)
async def admit(data: AdmissionCreate,
                actor: CurrentUser = Depends(require_staff),
                svc: WardService = Depends(get_service)):
    return await svc.admit(data, actor)


@router.get("/admissions", response_model=list[AdmissionOut])
async def list_admissions(status: AdmissionStatus | None = Query(None),
                          patient_id: int | None = Query(None),
                          _: CurrentUser = Depends(require_staff),
                          svc: WardService = Depends(get_service)):
    return await svc.list_admissions(status, patient_id)


@router.get("/admissions/{admission_id}")
async def get_admission(admission_id: int,
                        _: CurrentUser = Depends(require_staff),
                        svc: WardService = Depends(get_service)):
    return await svc.get_admission(admission_id)


@router.post("/admissions/{admission_id}/discharge", response_model=AdmissionOut)
async def discharge(admission_id: int, data: DischargeIn,
                    actor: CurrentUser = Depends(require_staff),
                    svc: WardService = Depends(get_service)):
    return await svc.discharge(admission_id, data, actor)


@router.post("/care-logs", status_code=201)
async def add_care_log(data: CareLogCreate,
                       actor: CurrentUser = Depends(require_staff),
                       svc: WardService = Depends(get_service)):
    return await svc.add_care_log(data, actor)


@router.get("/admissions/{admission_id}/care-logs")
async def list_care_logs(admission_id: int,
                         _: CurrentUser = Depends(require_staff),
                         svc: WardService = Depends(get_service)):
    return await svc.list_care_logs(admission_id)


# ------------------------------------------------------------------------ OT
@router.get("/ot/theatres", response_model=list[TheatreOut])
async def theatres(_: CurrentUser = Depends(require_staff),
                   svc: WardService = Depends(get_service)):
    return [{"id": t.id, "name": t.name, "category": t.category.value,
             "status": t.status.value, "equipment": t.equipment}
            for t in await svc.list_theatres()]


@router.post("/ot/surgeries", response_model=SurgeryOut, status_code=201)
async def schedule_surgery(data: SurgeryCreate,
                           actor: CurrentUser = Depends(require_admin),
                           svc: WardService = Depends(get_service)):
    return await svc.schedule_surgery(data, actor)


@router.get("/ot/surgeries", response_model=list[SurgeryOut])
async def list_surgeries(status: SurgeryStatus | None = Query(None),
                         _: CurrentUser = Depends(require_staff),
                         svc: WardService = Depends(get_service)):
    return await svc.list_surgeries(status)


@router.patch("/ot/surgeries/{surgery_id}/status")
async def set_surgery_status(surgery_id: int, data: SurgeryStatusIn,
                             actor: CurrentUser = Depends(require_staff),
                             svc: WardService = Depends(get_service)):
    return await svc.set_surgery_status(surgery_id, data, actor)
