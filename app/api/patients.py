"""
REST API routes for patient management.

All responses follow the envelope:
  success → {"data": {...},  "error": null}
  error   → {"data": null,   "error": {"message": "...", "details": ...}}
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.patient import (
    PatientCreate,
    PatientListResponse,
    PatientResponse,
    PatientUpdate,
    error_response,
    success_response,
)
from app.services import patient_service as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["Patients"])


# ── GET /patients ──────────────────────────────────────────────────────────────
@router.get(
    "",
    summary="List active patients",
    response_description="Paginated list of active patients",
)
def list_patients(
    last_name: Optional[str] = Query(None, description="Filter by last name (partial match)"),
    date_of_birth: Optional[str] = Query(None, description="Filter by DOB (YYYY-MM-DD)"),
    phone_number: Optional[str] = Query(None, description="Filter by phone number"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    records, total = svc.list_patients(
        db,
        last_name=last_name,
        date_of_birth=date_of_birth,
        phone_number=phone_number,
        skip=skip,
        limit=limit,
    )
    patients = [PatientResponse.model_validate(r) for r in records]
    return success_response({"total": total, "patients": [p.model_dump(mode="json") for p in patients]})


# ── GET /patients/{id} ─────────────────────────────────────────────────────────
@router.get(
    "/{patient_id}",
    summary="Get a patient by UUID",
)
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = svc.get_patient(db, patient_id)
    if patient is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response("Patient not found.", {"patient_id": patient_id}),
        )
    return success_response(PatientResponse.model_validate(patient).model_dump(mode="json"))


# ── POST /patients ─────────────────────────────────────────────────────────────
@router.post(
    "",
    summary="Create a new patient",
    status_code=status.HTTP_201_CREATED,
)
def create_patient(patient_in: PatientCreate, db: Session = Depends(get_db)):
    patient, is_duplicate = svc.create_patient(db, patient_in)

    if is_duplicate:
        # Return 409 so Vapi/caller knows registration already exists
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_response(
                "A patient with this phone number is already registered.",
                {"patient_id": patient.patient_id},
            ),
        )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=success_response(PatientResponse.model_validate(patient).model_dump(mode="json")),
    )


# ── PUT /patients/{id} ─────────────────────────────────────────────────────────
@router.put(
    "/{patient_id}",
    summary="Update a patient (partial update supported)",
)
def update_patient(
    patient_id: str, patient_in: PatientUpdate, db: Session = Depends(get_db)
):
    updated = svc.update_patient(db, patient_id, patient_in)
    if updated is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response("Patient not found.", {"patient_id": patient_id}),
        )
    return success_response(PatientResponse.model_validate(updated).model_dump(mode="json"))


# ── DELETE /patients/{id} ──────────────────────────────────────────────────────
@router.delete(
    "/{patient_id}",
    summary="Soft-delete a patient",
)
def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    deleted = svc.soft_delete_patient(db, patient_id)
    if deleted is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response("Patient not found.", {"patient_id": patient_id}),
        )
    return success_response(
        {
            "message": "Patient successfully deleted.",
            "patient_id": deleted.patient_id,
            "deleted_at": deleted.deleted_at.isoformat() if deleted.deleted_at else None,
        }
    )
