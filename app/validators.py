"""
CareCloud — Input Validation Layer
All validation is done server-side; the voice agent is a UX layer, not a trust boundary.
"""
import re
from datetime import date, datetime
from typing import Optional, Tuple

US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC","PR","GU","VI","AS","MP",
}


def validate_name(value: str, field: str) -> Tuple[bool, Optional[str]]:
    if not value or not (1 <= len(value.strip()) <= 50):
        return False, f"{field} must be 1–50 characters."
    if not re.match(r"^[A-Za-z\-']+$", value.strip()):
        return False, f"{field} may only contain letters, hyphens, and apostrophes."
    return True, None


def validate_dob(value: str) -> Tuple[bool, Optional[str], Optional[date]]:
    """Accepts MM/DD/YYYY or YYYY-MM-DD."""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value.strip(), fmt).date()
            if parsed >= date.today():
                return False, "Date of birth cannot be today or in the future.", None
            return True, None, parsed
        except ValueError:
            continue
    return False, "Invalid date format. Use MM/DD/YYYY.", None


def validate_phone(value: str) -> Tuple[bool, Optional[str], Optional[str]]:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10:
        return False, "Phone number must be a valid 10-digit U.S. number.", None
    return True, None, digits


def validate_email(value: str) -> Tuple[bool, Optional[str]]:
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value.strip()):
        return False, "Invalid email format."
    return True, None


def validate_state(value: str) -> Tuple[bool, Optional[str]]:
    if value.strip().upper() not in US_STATES:
        return False, f"'{value}' is not a valid 2-letter U.S. state abbreviation."
    return True, None


def validate_zip(value: str) -> Tuple[bool, Optional[str]]:
    if not re.match(r"^\d{5}(-\d{4})?$", value.strip()):
        return False, "ZIP code must be 5 digits or ZIP+4 format (e.g., 10001 or 10001-1234)."
    return True, None


def validate_sex(value: str) -> Tuple[bool, Optional[str], Optional[str]]:
    mapping = {
        "male": "Male",
        "female": "Female",
        "other": "Other",
        "decline": "Decline to Answer",
        "decline to answer": "Decline to Answer",
        "prefer not to say": "Decline to Answer",
    }
    normalized = mapping.get(value.strip().lower())
    if not normalized:
        return False, "Sex must be Male, Female, Other, or Decline to Answer.", None
    return True, None, normalized


def validate_patient_payload(data: dict, partial: bool = False) -> Tuple[bool, dict, list]:
    """
    Validates patient create/update payload.
    Returns (is_valid, cleaned_data, errors_list).
    """
    errors = []
    cleaned = {}

    required = [
        "first_name", "last_name", "date_of_birth", "sex",
        "phone_number", "address_line_1", "city", "state", "zip_code"
    ]

    # --- Required fields ---
    for field in ["first_name", "last_name"]:
        if field in data:
            ok, err = validate_name(data[field], field)
            if ok:
                cleaned[field] = data[field].strip()
            else:
                errors.append({"field": field, "message": err})
        elif not partial:
            errors.append({"field": field, "message": f"{field} is required."})

    if "date_of_birth" in data:
        ok, err, parsed = validate_dob(data["date_of_birth"])
        if ok:
            cleaned["date_of_birth"] = parsed
        else:
            errors.append({"field": "date_of_birth", "message": err})
    elif not partial:
        errors.append({"field": "date_of_birth", "message": "date_of_birth is required."})

    if "sex" in data:
        ok, err, normalized = validate_sex(data["sex"])
        if ok:
            cleaned["sex"] = normalized
        else:
            errors.append({"field": "sex", "message": err})
    elif not partial:
        errors.append({"field": "sex", "message": "sex is required."})

    if "phone_number" in data:
        ok, err, digits = validate_phone(data["phone_number"])
        if ok:
            cleaned["phone_number"] = digits
        else:
            errors.append({"field": "phone_number", "message": err})
    elif not partial:
        errors.append({"field": "phone_number", "message": "phone_number is required."})

    for field in ["address_line_1", "city"]:
        if field in data:
            val = data[field].strip()
            if 1 <= len(val) <= 200:
                cleaned[field] = val
            else:
                errors.append({"field": field, "message": f"{field} must be 1–200 characters."})
        elif not partial:
            errors.append({"field": field, "message": f"{field} is required."})

    if "state" in data:
        ok, err = validate_state(data["state"])
        if ok:
            cleaned["state"] = data["state"].strip().upper()
        else:
            errors.append({"field": "state", "message": err})
    elif not partial:
        errors.append({"field": "state", "message": "state is required."})

    if "zip_code" in data:
        ok, err = validate_zip(data["zip_code"])
        if ok:
            cleaned["zip_code"] = data["zip_code"].strip()
        else:
            errors.append({"field": "zip_code", "message": err})
    elif not partial:
        errors.append({"field": "zip_code", "message": "zip_code is required."})

    # --- Optional fields ---
    if "email" in data and data["email"]:
        ok, err = validate_email(data["email"])
        if ok:
            cleaned["email"] = data["email"].strip().lower()
        else:
            errors.append({"field": "email", "message": err})

    if "address_line_2" in data:
        cleaned["address_line_2"] = data["address_line_2"].strip() if data["address_line_2"] else None

    if "insurance_provider" in data:
        cleaned["insurance_provider"] = data["insurance_provider"].strip() if data["insurance_provider"] else None

    if "insurance_member_id" in data:
        cleaned["insurance_member_id"] = data["insurance_member_id"].strip() if data["insurance_member_id"] else None

    if "preferred_language" in data:
        cleaned["preferred_language"] = data["preferred_language"].strip() if data["preferred_language"] else "English"

    if "emergency_contact_name" in data:
        cleaned["emergency_contact_name"] = data["emergency_contact_name"].strip() if data["emergency_contact_name"] else None

    if "emergency_contact_phone" in data and data["emergency_contact_phone"]:
        ok, err, digits = validate_phone(data["emergency_contact_phone"])
        if ok:
            cleaned["emergency_contact_phone"] = digits
        else:
            errors.append({"field": "emergency_contact_phone", "message": err})

    return len(errors) == 0, cleaned, errors
