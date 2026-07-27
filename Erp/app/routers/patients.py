from __future__ import annotations

from datetime import date

from fastapi import (APIRouter, Depends, File, Form, Query, UploadFile)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (CurrentUser, require_admin, require_any,
                           require_staff)
from app.models.enums import DocumentType
from app.schemas.patient import (ConsultationCreate, ConsultationOut,
                                 DocumentOut, PatientCreate, PatientOut,
                                 PatientUpdate, PhysioPlanCreate,
                                 PhysioPlanOut, PhysioSessionCreate)
from app.services.patient_service import PatientService
from app.utils.files import resolve_stored

router = APIRouter(prefix="/api", tags=["patients"])


def get_service(db: AsyncSession = Depends(get_db)) -> PatientService:
    return PatientService(db)


# ------------------------------------------------------------------ patients
@router.post("/patients", response_model=PatientOut, status_code=201)
async def create_patient(data: PatientCreate,
                         actor: CurrentUser = Depends(require_staff),
                         svc: PatientService = Depends(get_service)):
    return await svc.create_patient(data, actor)


@router.get("/patients", response_model=list[PatientOut])
async def search_patients(q: str = Query("", max_length=80),
                          _: CurrentUser = Depends(require_staff),
                          svc: PatientService = Depends(get_service)):
    return await svc.search(q)


@router.get("/patients/{patient_id}", response_model=PatientOut)
async def get_patient(patient_id: int,
                      actor: CurrentUser = Depends(require_any),
                      svc: PatientService = Depends(get_service)):
    return await svc.get_patient(patient_id, actor)


@router.patch("/patients/{patient_id}", response_model=PatientOut)
async def update_patient(patient_id: int, data: PatientUpdate,
                         _: CurrentUser = Depends(require_staff),
                         svc: PatientService = Depends(get_service)):
    return await svc.update_patient(patient_id, data)


@router.post("/patients/{patient_id}/enable-login", response_model=PatientOut)
async def enable_login(patient_id: int, username: str = Form(...),
                       password: str = Form(...),
                       _: CurrentUser = Depends(require_staff),
                       svc: PatientService = Depends(get_service)):
    return await svc.enable_login(patient_id, username, password)


# ------------------------------------------------------------- consultations
@router.post("/consultations", response_model=ConsultationOut, status_code=201)
async def create_consultation(data: ConsultationCreate,
                              actor: CurrentUser = Depends(require_admin),
                              svc: PatientService = Depends(get_service)):
    return await svc.create_consultation(data, actor)


@router.get("/consultations", response_model=list[ConsultationOut])
async def list_consultations(patient_id: int | None = Query(None),
                             day: date | None = Query(None),
                             actor: CurrentUser = Depends(require_any),
                             svc: PatientService = Depends(get_service)):
    return await svc.list_consultations(actor, patient_id, day)


@router.get("/consultations/{consultation_id}", response_model=ConsultationOut)
async def get_consultation(consultation_id: int,
                           actor: CurrentUser = Depends(require_any),
                           svc: PatientService = Depends(get_service)):
    return await svc.get_consultation(consultation_id, actor)


# ----------------------------------------------------------------- documents
@router.post("/patients/{patient_id}/documents", response_model=DocumentOut,
             status_code=201)
async def upload_document(patient_id: int,
                          file: UploadFile = File(...),
                          doc_type: DocumentType = Form(...),
                          title: str = Form(..., min_length=2, max_length=120),
                          taken_on: date | None = Form(None),
                          notes: str = Form("", max_length=500),
                          actor: CurrentUser = Depends(require_staff),
                          svc: PatientService = Depends(get_service)):
    return await svc.upload_document(patient_id, file, doc_type, title,
                                     taken_on, notes, actor)


@router.get("/patients/{patient_id}/documents", response_model=list[DocumentOut])
async def list_documents(patient_id: int,
                         actor: CurrentUser = Depends(require_any),
                         svc: PatientService = Depends(get_service)):
    return await svc.list_documents(patient_id, actor)


@router.get("/documents/{doc_id}/download")
async def download_document(doc_id: int,
                            actor: CurrentUser = Depends(require_any),
                            svc: PatientService = Depends(get_service)):
    doc = await svc.get_document(doc_id, actor)
    path = resolve_stored(doc.file_path)
    return FileResponse(path, media_type=doc.content_type,
                        filename=doc.original_name,
                        content_disposition_type="inline")


# -------------------------------------------------------------------- physio
@router.post("/physio/plans", response_model=PhysioPlanOut, status_code=201)
async def create_plan(data: PhysioPlanCreate,
                      actor: CurrentUser = Depends(require_staff),
                      svc: PatientService = Depends(get_service)):
    return await svc.create_physio_plan(data, actor)


@router.get("/physio/plans", response_model=list[PhysioPlanOut])
async def list_plans(patient_id: int | None = Query(None),
                     actor: CurrentUser = Depends(require_any),
                     svc: PatientService = Depends(get_service)):
    return await svc.list_physio_plans(actor, patient_id)


@router.post("/physio/sessions", response_model=PhysioPlanOut, status_code=201)
async def add_session(data: PhysioSessionCreate,
                      actor: CurrentUser = Depends(require_staff),
                      svc: PatientService = Depends(get_service)):
    return await svc.add_physio_session(data, actor)
