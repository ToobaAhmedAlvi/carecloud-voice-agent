"""
CareCloud — Patient REST API
Endpoints: GET /patients, GET /patients/:id, POST /patients,
           PUT /patients/:id, DELETE /patients/:id (soft)
"""
import logging
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session

from app.models import Patient, SessionLocal, SexEnum
from app.validators import validate_patient_payload

log = logging.getLogger("carecloud.api")
patients_bp = Blueprint("patients", __name__, url_prefix="/patients")


def _db() -> Session:
    return SessionLocal()


def ok(data, status=200):
    return jsonify({"data": data, "error": None}), status


def err(message, status=400, details=None):
    return jsonify({"data": None, "error": {"message": message, "details": details}}), status


# ── GET /patients ─────────────────────────────────────────────────────────────
@patients_bp.route("", methods=["GET"])
def list_patients():
    db = _db()
    try:
        q = db.query(Patient).filter(Patient.deleted_at.is_(None))

        last_name = request.args.get("last_name")
        dob       = request.args.get("date_of_birth")
        phone     = request.args.get("phone_number")

        if last_name:
            q = q.filter(Patient.last_name.ilike(f"%{last_name}%"))
        if dob:
            from app.validators import validate_dob
            ok_flag, _, parsed = validate_dob(dob)
            if ok_flag:
                q = q.filter(Patient.date_of_birth == parsed)
        if phone:
            from app.validators import validate_phone
            ok_flag, _, digits = validate_phone(phone)
            if ok_flag:
                q = q.filter(Patient.phone_number == digits)

        patients = q.order_by(Patient.created_at.desc()).all()
        return ok([p.to_dict() for p in patients])
    finally:
        db.close()


# ── GET /patients/:id ─────────────────────────────────────────────────────────
@patients_bp.route("/<patient_id>", methods=["GET"])
def get_patient(patient_id):
    db = _db()
    try:
        patient = db.query(Patient).filter(
            Patient.patient_id == patient_id,
            Patient.deleted_at.is_(None)
        ).first()
        if not patient:
            return err("Patient not found.", 404)
        return ok(patient.to_dict())
    finally:
        db.close()


# ── POST /patients ────────────────────────────────────────────────────────────
@patients_bp.route("", methods=["POST"])
def create_patient():
    db = _db()
    try:
        body = request.get_json(force=True, silent=True) or {}
        is_valid, cleaned, errors = validate_patient_payload(body, partial=False)

        if not is_valid:
            return err("Validation failed.", 422, errors)

        # Duplicate detection by phone number
        existing = db.query(Patient).filter(
            Patient.phone_number == cleaned["phone_number"],
            Patient.deleted_at.is_(None)
        ).first()
        if existing:
            return jsonify({
                "data": existing.to_dict(),
                "error": None,
                "duplicate": True,
                "message": (
                    f"A patient record already exists for "
                    f"{existing.first_name} {existing.last_name} "
                    f"with this phone number."
                )
            }), 200

        # Map sex string to enum
        sex_map = {
            "Male": SexEnum.male,
            "Female": SexEnum.female,
            "Other": SexEnum.other,
            "Decline to Answer": SexEnum.decline,
        }
        cleaned["sex"] = sex_map[cleaned["sex"]]

        patient = Patient(**cleaned)
        db.add(patient)
        db.commit()
        db.refresh(patient)

        log.info("[PATIENT CREATED] %s", patient.to_dict())
        return ok(patient.to_dict(), 201)
    finally:
        db.close()


# ── PUT /patients/:id ─────────────────────────────────────────────────────────
@patients_bp.route("/<patient_id>", methods=["PUT"])
def update_patient(patient_id):
    db = _db()
    try:
        patient = db.query(Patient).filter(
            Patient.patient_id == patient_id,
            Patient.deleted_at.is_(None)
        ).first()
        if not patient:
            return err("Patient not found.", 404)

        body = request.get_json(force=True, silent=True) or {}
        is_valid, cleaned, errors = validate_patient_payload(body, partial=True)
        if not is_valid:
            return err("Validation failed.", 422, errors)

        # Map sex if present
        if "sex" in cleaned:
            sex_map = {
                "Male": SexEnum.male, "Female": SexEnum.female,
                "Other": SexEnum.other, "Decline to Answer": SexEnum.decline,
            }
            cleaned["sex"] = sex_map[cleaned["sex"]]

        for k, v in cleaned.items():
            setattr(patient, k, v)
        patient.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(patient)

        log.info("[PATIENT UPDATED] %s", patient.to_dict())
        return ok(patient.to_dict())
    finally:
        db.close()


# ── DELETE /patients/:id (soft delete) ───────────────────────────────────────
@patients_bp.route("/<patient_id>", methods=["DELETE"])
def delete_patient(patient_id):
    db = _db()
    try:
        patient = db.query(Patient).filter(
            Patient.patient_id == patient_id,
            Patient.deleted_at.is_(None)
        ).first()
        if not patient:
            return err("Patient not found.", 404)

        patient.deleted_at = datetime.now(timezone.utc)
        db.commit()

        log.info("[PATIENT SOFT-DELETED] patient_id=%s", patient_id)
        return ok({"patient_id": patient_id, "deleted": True})
    finally:
        db.close()
