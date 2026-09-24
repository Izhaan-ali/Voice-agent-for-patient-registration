"""
Service layer for patient business logic.

All database interaction goes through here — API routes stay thin.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.database.models import Patient
from app.schemas.patient import PatientCreate, PatientUpdate

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Read ───────────────────────────────────────────────────────────────────────

def get_patient(db: Session, patient_id: str) -> Optional[Patient]:
    """Return an active (non-deleted) patient by UUID, or None."""
    return (
        db.query(Patient)
        .filter(Patient.patient_id == patient_id, Patient.deleted_at.is_(None))
        .first()
    )


def find_patient_by_phone(db: Session, phone_number: str) -> Optional[Patient]:
    """
    Return the first active patient whose phone_number matches.
    phone_number must already be normalised to 10 digits.
    Used for duplicate detection and returning-caller lookup.
    """
    return (
        db.query(Patient)
        .filter(Patient.phone_number == phone_number, Patient.deleted_at.is_(None))
        .first()
    )


def list_patients(
    db: Session,
    last_name: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    phone_number: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Patient], int]:
    """
    Return active patients, optionally filtered by last_name / date_of_birth / phone_number.
    Returns (records, total_count).
    """
    query = db.query(Patient).filter(Patient.deleted_at.is_(None))

    if last_name:
        query = query.filter(Patient.last_name.ilike(f"%{last_name}%"))
    if date_of_birth:
        query = query.filter(Patient.date_of_birth == date_of_birth)
    if phone_number:
        # normalise digits only before comparing
        digits = "".join(c for c in phone_number if c.isdigit())
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        query = query.filter(Patient.phone_number == digits)

    total = query.count()
    records = query.order_by(Patient.created_at.desc()).offset(skip).limit(limit).all()
    return records, total


# ── Write ──────────────────────────────────────────────────────────────────────

def create_patient(db: Session, patient_in: PatientCreate) -> tuple[Patient, bool]:
    """
    Create a new patient record.

    Returns (patient, is_duplicate) where is_duplicate=True means a patient
    with the same phone number already exists (not created; existing returned).

    Duplicate detection is based on phone_number only (simple, per spec).
    """
    existing = find_patient_by_phone(db, patient_in.phone_number)
    if existing:
        logger.warning(
            "Duplicate registration attempt — phone %s already belongs to patient %s",
            patient_in.phone_number,
            existing.patient_id,
        )
        return existing, True

    data = patient_in.model_dump()
    db_patient = Patient(**data)
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)

    logger.info(
        "Patient created | id=%s name=%s %s phone=%s dob=%s sex=%s city=%s state=%s",
        db_patient.patient_id,
        db_patient.first_name,
        db_patient.last_name,
        db_patient.phone_number,
        db_patient.date_of_birth,
        db_patient.sex,
        db_patient.city,
        db_patient.state,
    )
    return db_patient, False


def update_patient(
    db: Session, patient_id: str, patient_in: PatientUpdate
) -> Optional[Patient]:
    """
    Partially update an active patient.  Only provided (non-None) fields are changed.
    Returns the updated patient, or None if not found / already deleted.
    """
    db_patient = get_patient(db, patient_id)
    if db_patient is None:
        return None

    update_data = patient_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_patient, field, value)

    db_patient.updated_at = _utcnow()
    db.commit()
    db.refresh(db_patient)

    logger.info(
        "Patient updated | id=%s fields=%s",
        db_patient.patient_id,
        list(update_data.keys()),
    )
    return db_patient


def soft_delete_patient(db: Session, patient_id: str) -> Optional[Patient]:
    """
    Soft-delete: set deleted_at to UTC now.  Record is never physically removed.
    Returns the patient record after marking, or None if not found.
    """
    db_patient = get_patient(db, patient_id)
    if db_patient is None:
        return None

    db_patient.deleted_at = _utcnow()
    db_patient.updated_at = _utcnow()
    db.commit()
    db.refresh(db_patient)

    logger.info("Patient soft-deleted | id=%s", db_patient.patient_id)
    return db_patient
