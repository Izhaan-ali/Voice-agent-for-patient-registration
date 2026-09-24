"""
Automated API test suite for the Voice AI Patient Registration backend.

Uses FastAPI TestClient with an isolated in-memory SQLite database so tests
are fully self-contained and never touch patients.db.

Coverage (per spec section 26):
  1.  Create valid patient
  2.  Reject invalid first_name
  3.  Reject invalid last_name
  4.  Reject future date_of_birth
  5.  Reject invalid sex
  6.  Reject invalid phone_number
  7.  Reject invalid state
  8.  Reject invalid zip_code
  9.  Create patient returns UUID
  10. Retrieve patient by ID
  11. List patients
  12. Update patient
  13. Soft-delete patient
  14. Deleted patient absent from active list
  15. Duplicate phone detection
  + additional edge-case and envelope checks
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import models BEFORE Base so they register with metadata
import app.database.models  # noqa: F401
from app.database.database import Base, get_db
from app.main import app

# ── In-memory test database ───────────────────────────────────────────────────
# StaticPool forces all engine connections to reuse the SAME underlying
# SQLite connection, so drop_all/create_all and the session override all
# see the same in-memory database.
TEST_DATABASE_URL = "sqlite:///:memory:"
_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

# Create tables ONCE at module load — they persist for the whole test session.
Base.metadata.create_all(bind=_engine)


def _override_get_db():
    db = _TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db():
    """Delete all patient rows before and after each test (fast truncate)."""
    from app.database.models import Patient
    db = _TestingSession()
    db.query(Patient).delete()
    db.commit()
    db.close()
    yield
    db2 = _TestingSession()
    db2.query(Patient).delete()
    db2.commit()
    db2.close()


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def valid_payload():
    return {
        "first_name": "Alice",
        "last_name": "Smith",
        "date_of_birth": "06/15/1985",
        "sex": "Female",
        "phone_number": "(415) 555-0100",
        "address_line_1": "100 Market St",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94105",
    }


@pytest.fixture
def created_patient(client, valid_payload):
    """Helper: POST a valid patient and return the response body."""
    r = client.post("/api/v1/patients", json=valid_payload)
    assert r.status_code == 201
    return r.json()["data"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def assert_envelope(body, expect_data=True, expect_error=False):
    """Assert the standard {data, error} envelope is present."""
    assert "data" in body, f"Missing 'data' key in: {body}"
    assert "error" in body, f"Missing 'error' key in: {body}"
    if expect_data:
        assert body["data"] is not None, f"Expected data, got None. Body: {body}"
    if expect_error:
        assert body["error"] is not None, f"Expected error, got None. Body: {body}"


# ══════════════════════════════════════════════════════════════════════════════
# 1. Create valid patient
# ══════════════════════════════════════════════════════════════════════════════

class TestCreatePatient:
    def test_create_valid_patient_returns_201(self, client, valid_payload):
        r = client.post("/api/v1/patients", json=valid_payload)
        assert r.status_code == 201

    def test_create_valid_patient_envelope(self, client, valid_payload):
        r = client.post("/api/v1/patients", json=valid_payload)
        assert_envelope(r.json(), expect_data=True)

    # 9. Create patient returns UUID
    def test_create_returns_uuid(self, client, valid_payload):
        r = client.post("/api/v1/patients", json=valid_payload)
        pid = r.json()["data"]["patient_id"]
        assert isinstance(pid, str) and len(pid) == 36
        # Basic UUID format check
        parts = pid.split("-")
        assert len(parts) == 5

    def test_create_auto_fields_populated(self, client, valid_payload):
        r = client.post("/api/v1/patients", json=valid_payload)
        data = r.json()["data"]
        assert data["created_at"] is not None
        assert data["updated_at"] is not None
        assert data["deleted_at"] is None

    def test_create_phone_normalised(self, client, valid_payload):
        r = client.post("/api/v1/patients", json=valid_payload)
        assert r.json()["data"]["phone_number"] == "4155550100"

    def test_create_dob_normalised(self, client, valid_payload):
        r = client.post("/api/v1/patients", json=valid_payload)
        assert r.json()["data"]["date_of_birth"] == "1985-06-15"

    def test_create_preferred_language_defaults_to_english(self, client, valid_payload):
        r = client.post("/api/v1/patients", json=valid_payload)
        assert r.json()["data"]["preferred_language"] == "English"

    def test_create_with_all_optional_fields(self, client, valid_payload):
        payload = {
            **valid_payload,
            "email": "alice@example.com",
            "address_line_2": "Apt 4B",
            "insurance_provider": "BlueCross",
            "insurance_member_id": "MEM123",
            "preferred_language": "Spanish",
            "emergency_contact_name": "Bob Smith",
            "emergency_contact_phone": "4155550200",
        }
        r = client.post("/api/v1/patients", json=payload)
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["email"] == "alice@example.com"
        assert data["insurance_member_id"] == "MEM123"

    def test_create_accepts_dob_iso_format(self, client, valid_payload):
        payload = {**valid_payload, "date_of_birth": "1985-06-15", "phone_number": "4155550111"}
        r = client.post("/api/v1/patients", json=payload)
        assert r.status_code == 201

    def test_create_with_empty_strings_for_optional_fields(self, client, valid_payload):
        payload = {
            **valid_payload,
            "phone_number": "4155550222",
            "email": "",
            "address_line_2": "",
            "insurance_provider": "",
            "insurance_member_id": "",
            "preferred_language": "",
            "emergency_contact_name": "",
            "emergency_contact_phone": "",
        }
        r = client.post("/api/v1/patients", json=payload)
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["email"] is None
        assert data["insurance_member_id"] is None
        assert data["emergency_contact_phone"] is None
        assert data["preferred_language"] == "English"



# ══════════════════════════════════════════════════════════════════════════════
# 2. Reject invalid first_name
# ══════════════════════════════════════════════════════════════════════════════

class TestFirstNameValidation:
    def test_reject_empty_first_name(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "first_name": ""})
        assert r.status_code == 422

    def test_reject_numeric_first_name(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "first_name": "J0hn"})
        assert r.status_code == 422

    def test_reject_first_name_too_long(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "first_name": "A" * 51})
        assert r.status_code == 422

    def test_accept_hyphenated_first_name(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "first_name": "Mary-Anne"})
        assert r.status_code == 201

    def test_accept_apostrophe_first_name(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "first_name": "O'Brien"})
        assert r.status_code == 201


# ══════════════════════════════════════════════════════════════════════════════
# 3. Reject invalid last_name
# ══════════════════════════════════════════════════════════════════════════════

class TestLastNameValidation:
    def test_reject_empty_last_name(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "last_name": ""})
        assert r.status_code == 422

    def test_reject_numeric_last_name(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "last_name": "Sm1th"})
        assert r.status_code == 422

    def test_accept_hyphenated_last_name(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "last_name": "Garcia-Lopez"})
        assert r.status_code == 201

    def test_accept_apostrophe_last_name(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "last_name": "O'Connor"})
        assert r.status_code == 201


# ══════════════════════════════════════════════════════════════════════════════
# 4. Reject future date_of_birth
# ══════════════════════════════════════════════════════════════════════════════

class TestDOBValidation:
    def test_reject_future_dob(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "date_of_birth": "01/01/2099"})
        assert r.status_code == 422

    def test_reject_invalid_dob_string(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "date_of_birth": "not-a-date"})
        assert r.status_code == 422

    def test_accept_past_dob_mm_dd_yyyy(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "date_of_birth": "03/12/1990"})
        assert r.status_code == 201

    def test_accept_past_dob_iso(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "date_of_birth": "1990-03-12", "phone_number": "4155550999"})
        assert r.status_code == 201


# ══════════════════════════════════════════════════════════════════════════════
# 5. Reject invalid sex
# ══════════════════════════════════════════════════════════════════════════════

class TestSexValidation:
    def test_reject_invalid_sex(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "sex": "Unknown"})
        assert r.status_code == 422

    def test_accept_male(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "sex": "Male"})
        assert r.status_code == 201

    def test_accept_female(self, client, valid_payload):
        r = client.post("/api/v1/patients", json=valid_payload)
        assert r.status_code == 201

    def test_accept_other(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "sex": "Other", "phone_number": "4155550300"})
        assert r.status_code == 201

    def test_accept_decline_to_answer(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "sex": "Decline to Answer", "phone_number": "4155550400"})
        assert r.status_code == 201


# ══════════════════════════════════════════════════════════════════════════════
# 6. Reject invalid phone_number
# ══════════════════════════════════════════════════════════════════════════════

class TestPhoneValidation:
    def test_reject_too_short(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "phone_number": "123"})
        assert r.status_code == 422

    def test_reject_letters(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "phone_number": "CALLMENOW"})
        assert r.status_code == 422

    def test_accept_dashes(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "phone_number": "415-555-0100"})
        assert r.status_code == 201

    def test_accept_parentheses_format(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "phone_number": "(415) 555-0100"})
        assert r.status_code == 201

    def test_accept_spaces(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "phone_number": "415 555 0100"})
        assert r.status_code == 201

    def test_phone_stored_as_10_digits(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "phone_number": "(415) 555-0100"})
        assert r.json()["data"]["phone_number"] == "4155550100"


# ══════════════════════════════════════════════════════════════════════════════
# 7. Reject invalid state
# ══════════════════════════════════════════════════════════════════════════════

class TestStateValidation:
    def test_reject_invalid_state(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "state": "XX"})
        assert r.status_code == 422

    def test_reject_full_state_name(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "state": "California"})
        assert r.status_code == 422

    def test_accept_valid_state(self, client, valid_payload):
        r = client.post("/api/v1/patients", json=valid_payload)
        assert r.status_code == 201

    def test_accept_lowercase_state_normalised(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "state": "ca"})
        assert r.status_code == 201
        assert r.json()["data"]["state"] == "CA"

    def test_accept_dc_territory(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "state": "DC", "phone_number": "2025550100"})
        assert r.status_code == 201


# ══════════════════════════════════════════════════════════════════════════════
# 8. Reject invalid zip_code
# ══════════════════════════════════════════════════════════════════════════════

class TestZipValidation:
    def test_reject_too_short(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "zip_code": "1234"})
        assert r.status_code == 422

    def test_reject_letters(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "zip_code": "ABCDE"})
        assert r.status_code == 422

    def test_accept_5_digit_zip(self, client, valid_payload):
        r = client.post("/api/v1/patients", json=valid_payload)
        assert r.status_code == 201

    def test_accept_zip_plus_4(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "zip_code": "94105-1234"})
        assert r.status_code == 201


# ══════════════════════════════════════════════════════════════════════════════
# 10. Retrieve patient
# ══════════════════════════════════════════════════════════════════════════════

class TestGetPatient:
    def test_get_existing_patient(self, client, created_patient):
        r = client.get(f"/api/v1/patients/{created_patient['patient_id']}")
        assert r.status_code == 200
        assert_envelope(r.json(), expect_data=True)
        assert r.json()["data"]["patient_id"] == created_patient["patient_id"]

    def test_get_returns_correct_fields(self, client, created_patient):
        r = client.get(f"/api/v1/patients/{created_patient['patient_id']}")
        data = r.json()["data"]
        assert data["first_name"] == "Alice"
        assert data["last_name"] == "Smith"

    def test_get_unknown_uuid_returns_404(self, client):
        r = client.get("/api/v1/patients/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404
        assert_envelope(r.json(), expect_data=False, expect_error=True)


# ══════════════════════════════════════════════════════════════════════════════
# 11. List patients
# ══════════════════════════════════════════════════════════════════════════════

class TestListPatients:
    def test_list_returns_200(self, client, created_patient):
        r = client.get("/api/v1/patients")
        assert r.status_code == 200

    def test_list_returns_envelope_with_total(self, client, created_patient):
        r = client.get("/api/v1/patients")
        data = r.json()["data"]
        assert "total" in data
        assert "patients" in data
        assert isinstance(data["patients"], list)

    def test_list_includes_created_patient(self, client, created_patient):
        r = client.get("/api/v1/patients")
        ids = [p["patient_id"] for p in r.json()["data"]["patients"]]
        assert created_patient["patient_id"] in ids

    def test_list_filter_by_last_name(self, client, created_patient):
        r = client.get("/api/v1/patients", params={"last_name": "Smith"})
        assert r.json()["data"]["total"] >= 1

    def test_list_filter_by_phone(self, client, created_patient):
        r = client.get("/api/v1/patients", params={"phone_number": "4155550100"})
        assert r.json()["data"]["total"] == 1

    def test_list_empty_db(self, client):
        r = client.get("/api/v1/patients")
        assert r.status_code == 200
        assert r.json()["data"]["total"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# 12. Update patient
# ══════════════════════════════════════════════════════════════════════════════

class TestUpdatePatient:
    def test_update_city(self, client, created_patient):
        r = client.put(
            f"/api/v1/patients/{created_patient['patient_id']}",
            json={"city": "Oakland"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["city"] == "Oakland"

    def test_update_preserves_untouched_fields(self, client, created_patient):
        client.put(
            f"/api/v1/patients/{created_patient['patient_id']}",
            json={"city": "Oakland"},
        )
        r = client.get(f"/api/v1/patients/{created_patient['patient_id']}")
        data = r.json()["data"]
        assert data["first_name"] == "Alice"   # untouched
        assert data["city"] == "Oakland"       # updated

    def test_update_unknown_returns_404(self, client):
        r = client.put(
            "/api/v1/patients/00000000-0000-0000-0000-000000000000",
            json={"city": "Anywhere"},
        )
        assert r.status_code == 404

    def test_update_with_invalid_state_returns_422(self, client, created_patient):
        r = client.put(
            f"/api/v1/patients/{created_patient['patient_id']}",
            json={"state": "ZZ"},
        )
        assert r.status_code == 422

    def test_update_phone_normalised(self, client, created_patient):
        r = client.put(
            f"/api/v1/patients/{created_patient['patient_id']}",
            json={"phone_number": "(510) 555-9999"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["phone_number"] == "5105559999"


# ══════════════════════════════════════════════════════════════════════════════
# 13. Soft-delete patient
# ══════════════════════════════════════════════════════════════════════════════

class TestSoftDeletePatient:
    def test_delete_returns_200(self, client, created_patient):
        r = client.delete(f"/api/v1/patients/{created_patient['patient_id']}")
        assert r.status_code == 200

    def test_delete_response_has_deleted_at(self, client, created_patient):
        r = client.delete(f"/api/v1/patients/{created_patient['patient_id']}")
        assert r.json()["data"]["deleted_at"] is not None

    def test_delete_unknown_returns_404(self, client):
        r = client.delete("/api/v1/patients/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    # 14. Deleted patient absent from active list
    def test_deleted_patient_absent_from_list(self, client, created_patient):
        client.delete(f"/api/v1/patients/{created_patient['patient_id']}")
        r = client.get("/api/v1/patients")
        ids = [p["patient_id"] for p in r.json()["data"]["patients"]]
        assert created_patient["patient_id"] not in ids
        assert r.json()["data"]["total"] == 0

    def test_deleted_patient_returns_404_on_get(self, client, created_patient):
        client.delete(f"/api/v1/patients/{created_patient['patient_id']}")
        r = client.get(f"/api/v1/patients/{created_patient['patient_id']}")
        assert r.status_code == 404

    def test_physical_row_still_exists_after_delete(self, client, created_patient):
        """Verify soft-delete does NOT physically remove the row."""
        client.delete(f"/api/v1/patients/{created_patient['patient_id']}")
        db = _TestingSession()
        from app.database.models import Patient
        row = db.query(Patient).filter(
            Patient.patient_id == created_patient["patient_id"]
        ).first()
        assert row is not None
        assert row.deleted_at is not None
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# 15. Duplicate phone detection
# ══════════════════════════════════════════════════════════════════════════════

class TestDuplicateDetection:
    def test_duplicate_phone_returns_409(self, client, valid_payload, created_patient):
        r = client.post(
            "/api/v1/patients",
            json={**valid_payload, "first_name": "Bob"},  # same phone
        )
        assert r.status_code == 409

    def test_duplicate_409_has_error_envelope(self, client, valid_payload, created_patient):
        r = client.post("/api/v1/patients", json={**valid_payload, "first_name": "Bob"})
        assert_envelope(r.json(), expect_data=False, expect_error=True)

    def test_duplicate_409_contains_existing_patient_id(self, client, valid_payload, created_patient):
        r = client.post("/api/v1/patients", json={**valid_payload, "first_name": "Bob"})
        details = r.json()["error"]["details"]
        assert details.get("patient_id") == created_patient["patient_id"]

    def test_different_phone_creates_new_patient(self, client, valid_payload, created_patient):
        r = client.post(
            "/api/v1/patients",
            json={**valid_payload, "phone_number": "5105550200"},
        )
        assert r.status_code == 201
        assert r.json()["data"]["patient_id"] != created_patient["patient_id"]


# ══════════════════════════════════════════════════════════════════════════════
# Response envelope consistency
# ══════════════════════════════════════════════════════════════════════════════

class TestResponseEnvelope:
    def test_success_envelope_has_null_error(self, client, created_patient):
        r = client.get(f"/api/v1/patients/{created_patient['patient_id']}")
        assert r.json()["error"] is None

    def test_error_envelope_has_null_data(self, client):
        r = client.get("/api/v1/patients/00000000-0000-0000-0000-000000000000")
        assert r.json()["data"] is None

    def test_422_envelope_has_details(self, client, valid_payload):
        r = client.post("/api/v1/patients", json={**valid_payload, "sex": "Robot"})
        assert r.status_code == 422
        assert r.json()["error"]["details"] is not None

    def test_health_endpoint(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "ok"
