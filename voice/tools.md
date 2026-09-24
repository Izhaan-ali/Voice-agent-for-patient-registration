# Vapi Tools & API Function Definitions

This document outlines the OpenAPI / Vapi Tool function definitions configured for the Patient Registration Assistant.

---

## 1. `create_patient` Tool Definition

**Description:** Register a new patient in the system. ONLY call this after explicit caller confirmation of full readback.

**HTTP Method:** `POST`  
**Endpoint:** `https://<YOUR-BACKEND-DOMAIN>/patients`

### JSON Schema (Vapi Function Call / OpenAI Tool Format)

```json
{
  "type": "function",
  "function": {
    "name": "create_patient",
    "description": "Creates a new patient registration record in the database. DO NOT call this tool until all required fields are collected and the caller has explicitly confirmed the full readback summary.",
    "parameters": {
      "type": "object",
      "properties": {
        "first_name": {
          "type": "string",
          "description": "Patient's first name (1-50 alphabetic characters, spaces, hyphens, apostrophes allowed)"
        },
        "last_name": {
          "type": "string",
          "description": "Patient's last name (1-50 alphabetic characters, spaces, hyphens, apostrophes allowed)"
        },
        "date_of_birth": {
          "type": "string",
          "description": "Date of birth in YYYY-MM-DD format (must be a valid past date)"
        },
        "sex": {
          "type": "string",
          "enum": ["male", "female", "non-binary", "prefer_not_to_say", "other"],
          "description": "Biological sex or gender identity"
        },
        "phone_number": {
          "type": "string",
          "description": "10-digit US phone number (e.g. 5551234567 or +15551234567)"
        },
        "address_line_1": {
          "type": "string",
          "description": "Primary street address"
        },
        "city": {
          "type": "string",
          "description": "City name"
        },
        "state": {
          "type": "string",
          "description": "2-letter US state code (e.g. CA, NY, TX)"
        },
        "zip_code": {
          "type": "string",
          "description": "5-digit or 5+4 US ZIP code"
        },
        "email": {
          "type": "string",
          "description": "Optional email address"
        },
        "address_line_2": {
          "type": "string",
          "description": "Optional apartment, suite, or unit number"
        },
        "insurance_provider": {
          "type": "string",
          "description": "Optional insurance provider name"
        },
        "insurance_member_id": {
          "type": "string",
          "description": "Optional insurance member ID"
        },
        "preferred_language": {
          "type": "string",
          "description": "Optional preferred language"
        },
        "emergency_contact_name": {
          "type": "string",
          "description": "Optional emergency contact name"
        },
        "emergency_contact_phone": {
          "type": "string",
          "description": "Optional emergency contact phone number"
        }
      },
      "required": [
        "first_name",
        "last_name",
        "date_of_birth",
        "sex",
        "phone_number",
        "address_line_1",
        "city",
        "state",
        "zip_code"
      ]
    }
  }
}
```

---

## 2. `get_patient_by_phone` Tool Definition

**Description:** Lookup an existing active patient by phone number.

**HTTP Method:** `GET`  
**Endpoint:** `https://<YOUR-BACKEND-DOMAIN>/patients?phone_number={phone_number}`

```json
{
  "type": "function",
  "function": {
    "name": "get_patient_by_phone",
    "description": "Searches for an existing patient registration using their phone number.",
    "parameters": {
      "type": "object",
      "properties": {
        "phone_number": {
          "type": "string",
          "description": "The 10-digit US phone number to query"
        }
      },
      "required": ["phone_number"]
    }
  }
}
```

---

## 3. `update_patient` Tool Definition

**Description:** Update an existing patient's details by `patient_id`.

**HTTP Method:** `PUT`  
**Endpoint:** `https://<YOUR-BACKEND-DOMAIN>/patients/{patient_id}`

```json
{
  "type": "function",
  "function": {
    "name": "update_patient",
    "description": "Updates details for an existing registered patient after full caller confirmation.",
    "parameters": {
      "type": "object",
      "properties": {
        "patient_id": {
          "type": "string",
          "description": "The UUID patient ID to update"
        },
        "first_name": { "type": "string" },
        "last_name": { "type": "string" },
        "date_of_birth": { "type": "string" },
        "sex": { "type": "string" },
        "phone_number": { "type": "string" },
        "address_line_1": { "type": "string" },
        "city": { "type": "string" },
        "state": { "type": "string" },
        "zip_code": { "type": "string" },
        "email": { "type": "string" },
        "address_line_2": { "type": "string" },
        "insurance_provider": { "type": "string" },
        "insurance_member_id": { "type": "string" },
        "preferred_language": { "type": "string" },
        "emergency_contact_name": { "type": "string" },
        "emergency_contact_phone": { "type": "string" }
      },
      "required": ["patient_id"]
    }
  }
}
```
