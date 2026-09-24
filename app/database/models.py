import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import CHAR

from app.database.database import Base

# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ── Model ─────────────────────────────────────────────────────────────────────

class Patient(Base):
    """
    Persistent patient record.

    Required fields  : first_name, last_name, date_of_birth, sex,
                       phone_number, address_line_1, city, state, zip_code
    Optional fields  : email, address_line_2, insurance_provider,
                       insurance_member_id, preferred_language,
                       emergency_contact_name, emergency_contact_phone
    Automatic fields : patient_id (UUID), created_at, updated_at, deleted_at
    """

    __tablename__ = "patients"

    # ── Automatic / primary key ───────────────────────────────────────────────
    patient_id = Column(
        CHAR(36),
        primary_key=True,
        default=_new_uuid,
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # ── Required fields ───────────────────────────────────────────────────────
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    date_of_birth = Column(String(10), nullable=False)   # stored as YYYY-MM-DD
    sex = Column(
        Enum("Male", "Female", "Other", "Decline to Answer", name="sex_enum"),
        nullable=False,
    )
    phone_number = Column(String(15), nullable=False, index=True)   # normalised: 10 digits
    address_line_1 = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(2), nullable=False)      # two-letter US abbreviation
    zip_code = Column(String(10), nullable=False)  # 12345 or 12345-6789

    # ── Optional fields ───────────────────────────────────────────────────────
    email = Column(String(255), nullable=True)
    address_line_2 = Column(String(255), nullable=True)
    insurance_provider = Column(String(100), nullable=True)
    insurance_member_id = Column(String(50), nullable=True)
    preferred_language = Column(String(50), nullable=True, default="English")
    emergency_contact_name = Column(String(101), nullable=True)
    emergency_contact_phone = Column(String(15), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Patient id={self.patient_id!r} "
            f"name={self.first_name!r} {self.last_name!r}>"
        )
