"""
CareCloud — Vapi Webhook Handler
KEY FIX: All tool handlers write DIRECTLY to the database.
No HTTP loopback calls — avoids Flask single-thread deadlock/timeout.
"""
import json
import logging
import os
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

from app.models import SessionLocal, Patient, SexEnum
from app.validators import validate_phone, validate_patient_payload

log = logging.getLogger("carecloud.vapi")
vapi_bp = Blueprint("vapi", __name__)

BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")

SYSTEM_PROMPT = """
You are Alex, a warm and professional patient registration coordinator for CareCloud Medical Group.
Your job is to register new patients over the phone by collecting their demographic information in a
natural, conversational way — like a friendly human intake coordinator, never a robotic IVR.

## PERSONALITY
- Warm, empathetic, clear. Use natural speech patterns like "Got it!", "Perfect!", "No problem at all."
- Speak in short sentences — remember this is audio, not text.
- NEVER read out JSON, code, or field names literally to the patient.

## FLOW
STEP 1 — PHONE CHECK
  Ask for callback phone number first. Use tool: lookup_patient_by_phone.
  If found: offer to update existing record.
  If not found: proceed with new registration.

STEP 2 — NAME: Collect first and last name. Spell back if unclear.

STEP 3 — DATE OF BIRTH: Accept spoken dates, convert to MM/DD/YYYY. Re-prompt if future date.

STEP 4 — SEX: Male, Female, Other, or Decline to Answer.

STEP 5 — ADDRESS: Street, apt/suite, city, state (2-letter), ZIP code.

STEP 6 — OPTIONAL: Offer email, insurance info, emergency contact as a group opt-in.

STEP 7 — CONFIRMATION: Read back ALL collected fields naturally. Ask to confirm or correct.

STEP 8 — SAVE: Only after explicit confirmation, call save_patient tool.

STEP 9 — CLOSING: "You are all set, [First Name]! Your patient ID is [patient_id]. Welcome to CareCloud!"

## ERROR HANDLING
- Invalid phone: re-prompt specifically
- Future date of birth: re-prompt
- Invalid state: ask for 2-letter abbreviation
- Invalid ZIP: ask for 5 digits
- Start over request: reset all data

## RULES
- NEVER save without explicit caller confirmation
- NEVER read JSON or field names to the caller
- Speak in short sentences - this is audio
- If caller speaks Spanish, switch entirely to Spanish
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_patient_by_phone",
            "description": "Look up an existing patient by phone number at the start of every call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone_number": {"type": "string", "description": "10-digit U.S. phone number"}
                },
                "required": ["phone_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_patient",
            "description": "Save new patient after caller confirms all information. Only call after explicit confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name":               {"type": "string"},
                    "last_name":                {"type": "string"},
                    "date_of_birth":            {"type": "string", "description": "MM/DD/YYYY"},
                    "sex":                      {"type": "string", "enum": ["Male","Female","Other","Decline to Answer"]},
                    "phone_number":             {"type": "string", "description": "10 digits only"},
                    "address_line_1":           {"type": "string"},
                    "address_line_2":           {"type": "string"},
                    "city":                     {"type": "string"},
                    "state":                    {"type": "string", "description": "2-letter abbreviation"},
                    "zip_code":                 {"type": "string"},
                    "email":                    {"type": "string"},
                    "insurance_provider":       {"type": "string"},
                    "insurance_member_id":      {"type": "string"},
                    "preferred_language":       {"type": "string"},
                    "emergency_contact_name":   {"type": "string"},
                    "emergency_contact_phone":  {"type": "string"},
                },
                "required": ["first_name","last_name","date_of_birth","sex","phone_number","address_line_1","city","state","zip_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_patient",
            "description": "Update an existing patient record for returning callers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "first_name": {"type": "string"},
                    "last_name":  {"type": "string"},
                    "address_line_1": {"type": "string"},
                    "address_line_2": {"type": "string"},
                    "city":       {"type": "string"},
                    "state":      {"type": "string"},
                    "zip_code":   {"type": "string"},
                    "email":      {"type": "string"},
                    "insurance_provider":      {"type": "string"},
                    "insurance_member_id":     {"type": "string"},
                    "emergency_contact_name":  {"type": "string"},
                    "emergency_contact_phone": {"type": "string"},
                },
                "required": ["patient_id"]
            }
        }
    }
]


def build_assistant_config():
    return {
        "name": "CareCloud-agent",
        "firstMessage": (
            "Thank you for calling CareCloud Medical Group. "
            "I'm Alex, and I'll be helping you register today. "
            "May I start with your callback phone number, in case we get disconnected?"
        ),
        "model": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
            "tools": TOOLS,
            "temperature": 0.3,
        },
        "voice": {
            "provider": "vapi",
            "voiceId": "Elliot",
        },
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 1800,
        "endCallFunctionEnabled": True,
        "endCallMessage": "Thank you for calling CareCloud Medical Group. Have a wonderful day!",
        "serverUrl": f"{BASE_URL}/webhook",
    }


# ── TOOL HANDLERS — direct DB, zero HTTP loopback ─────────────────────────

def handle_lookup_patient_by_phone(args: dict) -> dict:
    phone_raw = args.get("phone_number", "")
    ok_flag, _, digits = validate_phone(phone_raw)
    if not ok_flag:
        return {"found": False, "error": "Invalid phone number format."}
    db = SessionLocal()
    try:
        patient = db.query(Patient).filter(
            Patient.phone_number == digits,
            Patient.deleted_at.is_(None)
        ).first()
        if patient:
            log.info("[LOOKUP HIT] %s %s", patient.first_name, patient.last_name)
            return {
                "found": True,
                "patient_id": patient.patient_id,
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "message": f"Existing record found for {patient.first_name} {patient.last_name}."
            }
        return {"found": False, "message": "No existing record. Proceeding with new registration."}
    except Exception as e:
        log.exception("[LOOKUP ERROR] %s", e)
        return {"found": False, "error": "Database error during lookup."}
    finally:
        db.close()


def handle_save_patient(args: dict) -> dict:
    db = SessionLocal()
    try:
        is_valid, cleaned, errors = validate_patient_payload(args, partial=False)
        if not is_valid:
            log.error("[SAVE VALIDATION FAIL] %s", errors)
            first_err = errors[0]["message"] if errors else "Validation failed."
            return {"success": False, "error": first_err}

        existing = db.query(Patient).filter(
            Patient.phone_number == cleaned["phone_number"],
            Patient.deleted_at.is_(None)
        ).first()
        if existing:
            return {
                "success": True,
                "duplicate": True,
                "patient_id": existing.patient_id,
                "message": f"A record already exists for {existing.first_name} {existing.last_name}."
            }

        sex_map = {
            "Male": SexEnum.male, "Female": SexEnum.female,
            "Other": SexEnum.other, "Decline to Answer": SexEnum.decline,
        }
        cleaned["sex"] = sex_map.get(cleaned["sex"], SexEnum.decline)

        patient = Patient(**cleaned)
        db.add(patient)
        db.commit()
        db.refresh(patient)

        log.info("[PATIENT SAVED] %s %s → ID: %s",
                 patient.first_name, patient.last_name, patient.patient_id)
        return {
            "success": True,
            "patient_id": patient.patient_id,
            "message": f"Registration complete. Patient ID: {patient.patient_id}"
        }
    except Exception as e:
        db.rollback()
        log.exception("[SAVE ERROR] %s", e)
        return {"success": False, "error": "Database error. Please try again."}
    finally:
        db.close()


def handle_update_patient(args: dict) -> dict:
    patient_id = args.pop("patient_id", None)
    if not patient_id:
        return {"success": False, "error": "patient_id is required."}
    db = SessionLocal()
    try:
        patient = db.query(Patient).filter(
            Patient.patient_id == patient_id,
            Patient.deleted_at.is_(None)
        ).first()
        if not patient:
            return {"success": False, "error": "Patient not found."}

        is_valid, cleaned, errors = validate_patient_payload(args, partial=True)
        if not is_valid:
            return {"success": False, "error": errors[0]["message"] if errors else "Validation failed."}

        if "sex" in cleaned:
            sex_map = {
                "Male": SexEnum.male, "Female": SexEnum.female,
                "Other": SexEnum.other, "Decline to Answer": SexEnum.decline,
            }
            cleaned["sex"] = sex_map.get(cleaned["sex"], SexEnum.decline)

        for k, v in cleaned.items():
            setattr(patient, k, v)
        patient.updated_at = datetime.now(timezone.utc)
        db.commit()

        log.info("[PATIENT UPDATED] %s", patient_id)
        return {"success": True, "message": "Patient record updated successfully."}
    except Exception as e:
        db.rollback()
        log.exception("[UPDATE ERROR] %s", e)
        return {"success": False, "error": "Database error."}
    finally:
        db.close()


TOOL_HANDLERS = {
    "lookup_patient_by_phone": handle_lookup_patient_by_phone,
    "save_patient":            handle_save_patient,
    "update_patient":          handle_update_patient,
}


@vapi_bp.route("/webhook", methods=["POST"])
def webhook():
    payload  = request.get_json(force=True, silent=True) or {}
    message  = payload.get("message", {})
    msg_type = message.get("type", "")
    call_id  = message.get("call", {}).get("id", "n/a")

    log.info("[WEBHOOK] type=%s call_id=%s", msg_type, call_id)

    if msg_type == "assistant-request":
        return jsonify({"assistant": build_assistant_config()})

    if msg_type == "function-call":
        fn_call = message.get("functionCall", {})
        fn_name = fn_call.get("name", "")
        fn_args = fn_call.get("parameters", {})

        # Vapi can send parameters as string or dict
        if isinstance(fn_args, str):
            try:
                fn_args = json.loads(fn_args)
            except Exception:
                fn_args = {}

        # Fallback for some Vapi versions
        if not fn_args:
            fn_args = fn_call.get("arguments", {})
        if isinstance(fn_args, str):
            try:
                fn_args = json.loads(fn_args)
            except Exception:
                fn_args = {}

        log.info("[TOOL] %s args=%s", fn_name, json.dumps(fn_args, default=str))

        handler = TOOL_HANDLERS.get(fn_name)
        result  = handler(fn_args) if handler else {"error": f"Unknown function: {fn_name}"}

        log.info("[TOOL RESULT] %s => %s", fn_name, result)
        return jsonify({"result": result})

    if msg_type == "end-of-call-report":
        log.info("[CALL ENDED] call_id=%s summary=%s transcript=%s",
                 call_id, message.get("summary",""), message.get("transcript",""))
        return jsonify({"received": True})

    if msg_type == "status-update":
        log.info("[STATUS] %s call_id=%s", message.get("status",""), call_id)
        return jsonify({"received": True})

    if msg_type == "hang":
        log.warning("[HANG] call_id=%s", call_id)
        return jsonify({"received": True})

    return jsonify({"received": True})