"""
Pydantic schemas for patient creation, update, and API responses.

Validation is authoritative here — the backend never trusts LLM/Vapi output.
"""

import re
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ── US state abbreviations ────────────────────────────────────────────────────
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    # Territories recognised for the assessment
    "DC", "PR", "GU", "VI", "AS", "MP",
}

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z '\-]{0,49}$")
_PHONE_DIGITS_RE = re.compile(r"\D")          # strip non-digits
_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")
_ALNUM_RE = re.compile(r"^[A-Za-z0-9]+$")


# ── Enums ─────────────────────────────────────────────────────────────────────

class SexEnum(str, Enum):
    male = "Male"
    female = "Female"
    other = "Other"
    decline = "Decline to Answer"


# ── Shared validators (reused by Create & Update) ─────────────────────────────

def _validate_name(value: str, field_label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_label} must not be empty.")
    if len(value) > 50:
        raise ValueError(f"{field_label} must be 50 characters or fewer.")
    if not _NAME_RE.match(value):
        raise ValueError(
            f"{field_label} may only contain letters, hyphens, apostrophes, "
            f"and spaces, and must start with a letter."
        )
    return value


def _normalize_phone(value: str) -> str:
    """Strip formatting and validate that exactly 10 digits remain."""
    digits = _PHONE_DIGITS_RE.sub("", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]          # drop leading country code
    if len(digits) != 10:
        raise ValueError(
            "Phone number must be a valid U.S. 10-digit number "
            "(e.g. 415-555-1234 or (415) 555-1234)."
        )
    return digits                    # stored as plain 10 digits


def _validate_dob(value: str) -> str:
    """
    Accept MM/DD/YYYY or YYYY-MM-DD; normalise to YYYY-MM-DD.
    Reject future dates.
    """
    value = value.strip()
    parsed: Optional[date] = None

    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, fmt).date()
            break
        except ValueError:
            continue

    if parsed is None:
        raise ValueError(
            "date_of_birth must be in MM/DD/YYYY or YYYY-MM-DD format."
        )

    if parsed > date.today():
        raise ValueError("date_of_birth must not be in the future.")

    return parsed.isoformat()        # store as YYYY-MM-DD


def _validate_state(value: str) -> str:
    v = value.strip().upper()
    if v not in US_STATES:
        raise ValueError(
            f"state '{value}' is not a recognised U.S. state/territory abbreviation."
        )
    return v


def _validate_zip(value: str) -> str:
    v = value.strip()
    if not _ZIP_RE.match(v):
        raise ValueError(
            "zip_code must be in 12345 or 12345-6789 format."
        )
    return v


# ── PatientCreate ─────────────────────────────────────────────────────────────

class PatientCreate(BaseModel):
    """All required fields must be present and valid."""

    # Required
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    date_of_birth: str = Field(..., description="MM/DD/YYYY or YYYY-MM-DD")
    sex: SexEnum
    phone_number: str
    address_line_1: str = Field(..., min_length=1, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=2, max_length=2)
    zip_code: str

    # Optional
    email: Optional[EmailStr] = None
    address_line_2: Optional[str] = Field(default=None, max_length=255)
    insurance_provider: Optional[str] = Field(default=None, max_length=100)
    insurance_member_id: Optional[str] = Field(default=None, max_length=50)
    preferred_language: Optional[str] = Field(default="English", max_length=50)
    emergency_contact_name: Optional[str] = Field(default=None, max_length=101)
    emergency_contact_phone: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_empty_optional_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            optional_fields = {
                "email",
                "address_line_2",
                "insurance_provider",
                "insurance_member_id",
                "preferred_language",
                "emergency_contact_name",
                "emergency_contact_phone",
            }
            for field in optional_fields:
                if field in data and isinstance(data[field], str) and not data[field].strip():
                    data[field] = None
        return data

    # ── Field validators ──────────────────────────────────────────────────────
    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: str) -> str:
        return _validate_name(v, "first_name")

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: str) -> str:
        return _validate_name(v, "last_name")

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: str) -> str:
        return _validate_dob(v)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _normalize_phone(v)

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        return _validate_state(v)

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v: str) -> str:
        return _validate_zip(v)

    @field_validator("insurance_member_id")
    @classmethod
    def validate_insurance_member_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _ALNUM_RE.match(v):
            raise ValueError("insurance_member_id must be alphanumeric.")
        return v

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _normalize_phone(v)
        return v


# ── PatientUpdate ─────────────────────────────────────────────────────────────

class PatientUpdate(BaseModel):
    """All fields optional — only provided fields are updated."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    sex: Optional[SexEnum] = None
    phone_number: Optional[str] = None
    address_line_1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    email: Optional[EmailStr] = None
    address_line_2: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_empty_optional_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            optional_fields = {
                "email",
                "address_line_2",
                "insurance_provider",
                "insurance_member_id",
                "preferred_language",
                "emergency_contact_name",
                "emergency_contact_phone",
            }
            for field in optional_fields:
                if field in data and isinstance(data[field], str) and not data[field].strip():
                    data[field] = None
        return data

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: Optional[str]) -> Optional[str]:
        return _validate_name(v, "first_name") if v is not None else v

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: Optional[str]) -> Optional[str]:
        return _validate_name(v, "last_name") if v is not None else v

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: Optional[str]) -> Optional[str]:
        return _validate_dob(v) if v is not None else v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_phone(v) if v is not None else v

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: Optional[str]) -> Optional[str]:
        return _validate_state(v) if v is not None else v

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v: Optional[str]) -> Optional[str]:
        return _validate_zip(v) if v is not None else v

    @field_validator("insurance_member_id")
    @classmethod
    def validate_insurance_member_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _ALNUM_RE.match(v):
            raise ValueError("insurance_member_id must be alphanumeric.")
        return v

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_phone(v) if v is not None else v


# ── PatientResponse ───────────────────────────────────────────────────────────

class PatientResponse(BaseModel):
    """Returned by the API for a single patient."""

    patient_id: str
    first_name: str
    last_name: str
    date_of_birth: str
    sex: str
    phone_number: str
    address_line_1: str
    city: str
    state: str
    zip_code: str
    email: Optional[str] = None
    address_line_2: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── PatientListResponse ───────────────────────────────────────────────────────

class PatientListResponse(BaseModel):
    total: int
    patients: list[PatientResponse]


# ── API Envelope helpers ──────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    message: str
    details: Any = None


class APIResponse(BaseModel):
    """
    Standard envelope:
      success → {"data": {...}, "error": null}
      failure → {"data": null, "error": {"message": "...", "details": ...}}
    """
    data: Any = None
    error: Optional[ErrorDetail] = None


def success_response(data: Any) -> dict:
    return {"data": data, "error": None}


def error_response(message: str, details: Any = None) -> dict:
    return {"data": None, "error": {"message": message, "details": details}}
