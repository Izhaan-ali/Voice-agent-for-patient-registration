# Voice Agent for Patient Registration

An automated, conversational AI Voice Agent for patient intake and registration built with **FastAPI**, **SQLite**, **SQLAlchemy**, and **Vapi**. This system allows patients to complete medical registration over a natural phone call while enforcing strict data validation, privacy rules, prompt safety, and structured database persistence.

---

## 🏗️ Architecture

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│    Caller    │ ──────> │ Vapi Voice   │ ──────> │   FastAPI    │ ──────> │ SQLite DB    │
│  (Phone/Web) │ <────── │ Assistant    │ <────── │   Backend    │ <────── │ (patients.db)│
└──────────────┘         └──────────────┘         └──────────────┘         └──────────────┘
```

### Data Flow Overview
1. **Inbound / Outbound Call**: The patient dials a provisioned phone number connected to Vapi.
2. **Speech-to-Text & Intelligence**: Vapi processes speech using Whisper/LLM models and executes conversational dialog according to the system prompt.
3. **Existing Patient Search**: Vapi calls `GET /patients?phone_number=...` to check if the caller is already registered.
4. **Interactive Intake**: Vapi collects required and optional patient fields with real-time slot filling and error correction.
5. **Mandatory Confirmation**: Vapi performs a full readback of all collected fields and requests explicit caller confirmation ("Yes").
6. **Persistence**: Vapi calls `POST /patients` (or `PUT /patients/{id}`) to persist patient records in the SQLite database.
7. **Confirmation & Audio Response**: Vapi speaks the assigned `patient_id` to the caller upon HTTP 201 success.

---

## 🛠️ Tech Stack & Rationale

| Technology | Selection | Rationale |
|---|---|---|
| **Framework** | **FastAPI 0.115** | High-performance async Python API framework with automatic OpenAPI (`/docs`) generation, built-in Pydantic data validation, and minimal boilerplate. |
| **Voice Infrastructure** | **Vapi** | Leading voice AI orchestrator providing seamless telephony, low-latency STT/TTS pipeline integration, function calling tools, and call lifecycle management. |
| **Database** | **SQLite + SQLAlchemy 2.0** | Serverless, zero-configuration SQL database ideal for local storage and embedded deployments; paired with SQLAlchemy 2.0 ORM for clean schema definitions and transactions. |
| **Data Validation** | **Pydantic v2** | Strict static type checking, regex validation, custom validators for dates/phones/names, and response serialization. |
| **Testing** | **Pytest + StaticPool** | Comprehensive 70-test suite with isolated in-memory SQLite testing using `StaticPool` to prevent cross-connection isolation issues. |
| **Server Runner** | **Uvicorn + Gunicorn** | Production-ready ASGI server setup with worker process management for cloud deployment on Render/Railway. |

---

## 🚀 Local Setup Instructions

### Prerequisites
- **Python**: Version 3.10, 3.11, or 3.12
- **Git**

### 1. Clone & Navigate to Repository
```bash
git clone https://github.com/Izhaan-ali/Voice-agent-for-patient-registration.git
cd Voice-agent-for-patient-registration
```

### 2. Create & Activate Virtual Environment
```bash
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 5. Run Local Server
```bash
python run.py
```
Or directly with Uvicorn:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Access local interactive API docs at:  
👉 **http://127.0.0.1:8000/docs**  
👉 **http://127.0.0.1:8000/health**

---

## 🔑 Environment Variables

The application uses `pydantic-settings` to load settings from `.env`:

| Variable | Default Value | Description |
|---|---|---|
| `APP_NAME` | `"Patient Registration Voice Agent"` | Name of the FastAPI application |
| `ENV` | `"development"` | Environment (`development`, `staging`, `production`) |
| `DEBUG` | `true` | Enables verbose debug logs and Swagger UI |
| `HOST` | `"0.0.0.0"` | Host network interface binding |
| `PORT` | `8000` | HTTP port for backend server |
| `DATABASE_URL` | `"sqlite:///./patients.db"` | SQLite database connection string |
| `VAPI_API_KEY` | `""` | Vapi API Key for voice assistant integration |
| `VAPI_ASSISTANT_ID`| `""` | Vapi Assistant Identifier |

> ⚠️ **Security Note**: Never commit actual secrets or `.env` files containing production API keys to git repositories.

---

## 📡 API Endpoints

All responses follow a standard envelope: `{"success": true, "data": ..., "message": "...", "errors": null}`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check endpoint returning server status and uptime |
| `POST` | `/patients` | Register a new patient (HTTP 201) |
| `GET` | `/patients` | List patients with optional filtering (`phone_number`, `limit`, `offset`) |
| `GET` | `/patients/{id}` | Get patient details by UUID |
| `PUT` | `/patients/{id}` | Update existing patient details |
| `DELETE` | `/patients/{id}` | Soft delete patient record (sets `deleted_at`) |
| `GET` | `/docs` | Interactive Swagger UI API documentation |

---

## 🎙️ Vapi Voice Configuration

### 1. System Prompt (`voice/system_prompt.md`)
The assistant system prompt enforces:
- Conversational intake of required fields (*First Name, Last Name, DOB, Sex, Phone, Address, City, State, ZIP*).
- Normalization of spoken formats (e.g. states converted to 2-letter codes like `CA`).
- Correction handling and natural restart (`"start over"`).
- **Mandatory Readback Confirmation Rule**: DO NOT call `create_patient` until full summary is read back and explicitly confirmed with "Yes".

### 2. Tool Definitions (`voice/tools.md`)
The tool definition links Vapi to the production backend:
- `create_patient` ➔ `POST https://<YOUR-BACKEND-DOMAIN>/patients`
- `get_patient_by_phone` ➔ `GET https://<YOUR-BACKEND-DOMAIN>/patients?phone_number={phone_number}`
- `update_patient` ➔ `PUT https://<YOUR-BACKEND-DOMAIN>/patients/{id}`

### 3. Telephony Setup
1. Log in to [Vapi Dashboard](https://dashboard.vapi.ai).
2. Provision a US Phone Number.
3. Attach the Patient Registration Assistant to the provisioned phone number.
4. Set the Server URL to your deployed HTTPS domain (`https://<YOUR-BACKEND-DOMAIN>`).

---

## 🧪 Testing

### Automated Test Suite (70 Unit & Integration Tests)
Run pytest with full coverage report:
```bash
pytest -v
```

The test suite covers:
- **`TestCreatePatient`**: Valid patient creation, missing required fields, optional fields handling.
- **`TestFirstNameValidation` & `TestLastNameValidation`**: Invalid characters, numeric names, length limits.
- **`TestDOBValidation`**: Future DOB rejection, invalid format rejection, edge case valid past dates.
- **`TestSexValidation`**: Valid enum values (`male`, `female`, `non-binary`, `prefer_not_to_say`, `other`) & invalid sex values.
- **`TestPhoneValidation`**: 10-digit validation, short phone rejection, non-digit rejection.
- **`TestStateValidation` & `TestZipValidation`**: State codes (50 states) & ZIP formatting.
- **`TestRetrievePatient` & `TestListPatients`**: CRUD operations and pagination.
- **`TestUpdatePatient`**: Updating patient records and timestamp verification.
- **`TestSoftDeletePatient`**: Soft deletion (`deleted_at` timestamp) and filter verification.
- **`TestResponseEnvelope`**: Standardized JSON envelope format validation.

### Manual Voice Test Scenarios
1. **Normal Registration**: Speak all required fields ➔ Receive full readback ➔ Confirm ("Yes") ➔ Verified in database.
2. **Information Out of Order**: Provide address before name ➔ Agent collects remaining fields smoothly.
3. **Invalid Phone**: Provide 3-digit phone ➔ Agent prompts for valid 10-digit number.
4. **Future DOB**: Provide DOB in 2030 ➔ Agent states date is in future and re-prompts.
5. **Correction**: Provide wrong last name then correct it ➔ Agent saves corrected value.
6. **Optional Fields Declined**: Decline insurance/emergency contact ➔ Agent proceeds to confirmation.
7. **Confirmation Correction**: Say "No, my ZIP is 90211" during readback ➔ Agent updates ZIP and reconfirms.
8. **Start Over**: Say "I want to start over" ➔ Agent resets state and begins from step 1.
9. **Second Call**: Call again with same phone ➔ Agent recognizes existing patient.
10. **API Failure**: Simulate server error ➔ Agent gracefully notifies caller without claiming successful save.

---

## 🌐 Deployment (Render / Railway / Cloud)

### Deploying to Render
1. Push repository to GitHub.
2. Create a new **Web Service** on Render.
3. Connect repository and configure:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
4. Set Environment Variables in Render Dashboard (`DATABASE_URL`, `ENV=production`, `DEBUG=false`).
5. Deploy service and verify public access at `https://<your-app>.onrender.com/docs`.

---

## ⚖️ Architectural Tradeoffs

1. **Vapi vs. Custom WebSockets (Twilio + Whisper + Deepgram)**:
   - *Tradeoff*: Vapi handles latency, interruption logic (turn-taking), and STT/TTS pipeline orchestration out-of-the-box, allowing focus on business logic and data validation rather than socket state management.
2. **FastAPI vs. Flask / Django**:
   - *Tradeoff*: FastAPI offers native async performance and built-in Pydantic v2 data validation, which eliminates duplicate validation layers required in Flask.
3. **SQLite vs. PostgreSQL**:
   - *Tradeoff*: SQLite requires no external database instance or cloud hosting costs for development and single-server deployments. For high-concurrency production environments, switching `DATABASE_URL` to PostgreSQL requires zero code changes due to SQLAlchemy's abstraction layer.
4. **In-Memory SQLite Testing with `StaticPool`**:
   - *Tradeoff*: In-memory SQLite databases ordinarily spawn separate isolated DB connections per connection attempt. Using `StaticPool` forces all test connections to reuse a single shared in-memory database instance, guaranteeing zero test pollution while keeping test execution ultra-fast (<5s for 70 tests).
