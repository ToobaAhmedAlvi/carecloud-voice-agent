"""
CareCloud — API Test Suite
Run: python -m pytest tests/ -v
"""
import json
import pytest
import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["BASE_URL"]     = "http://localhost:5000"

from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Health ────────────────────────────────────────────────────────────────────
def test_health(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"CareCloud" in r.data


# ── Patient CRUD ──────────────────────────────────────────────────────────────
VALID_PATIENT = {
    "first_name":    "Test",
    "last_name":     "User",
    "date_of_birth": "01/15/1990",
    "sex":           "Male",
    "phone_number":  "5551234567",
    "address_line_1":"999 Test Street",
    "city":          "Austin",
    "state":         "TX",
    "zip_code":      "78701",
}


def test_create_patient(client):
    r = client.post("/patients", json=VALID_PATIENT)
    assert r.status_code == 201
    data = r.get_json()["data"]
    assert data["first_name"] == "Test"
    assert data["patient_id"] is not None


def test_list_patients(client):
    client.post("/patients", json=VALID_PATIENT)
    r = client.get("/patients")
    assert r.status_code == 200
    patients = r.get_json()["data"]
    assert len(patients) >= 1


def test_get_patient(client):
    create_r = client.post("/patients", json=VALID_PATIENT)
    pid = create_r.get_json()["data"]["patient_id"]
    r = client.get(f"/patients/{pid}")
    assert r.status_code == 200
    assert r.get_json()["data"]["patient_id"] == pid


def test_update_patient(client):
    create_r = client.post("/patients", json=VALID_PATIENT)
    pid = create_r.get_json()["data"]["patient_id"]
    r = client.put(f"/patients/{pid}", json={"city": "Houston"})
    assert r.status_code == 200
    assert r.get_json()["data"]["city"] == "Houston"


def test_soft_delete(client):
    create_r = client.post("/patients", json=VALID_PATIENT)
    pid = create_r.get_json()["data"]["patient_id"]
    r = client.delete(f"/patients/{pid}")
    assert r.status_code == 200
    # Should not appear in list
    list_r = client.get("/patients")
    ids = [p["patient_id"] for p in list_r.get_json()["data"]]
    assert pid not in ids


def test_get_deleted_patient_404(client):
    create_r = client.post("/patients", json=VALID_PATIENT)
    pid = create_r.get_json()["data"]["patient_id"]
    client.delete(f"/patients/{pid}")
    r = client.get(f"/patients/{pid}")
    assert r.status_code == 404


# ── Validation ────────────────────────────────────────────────────────────────
def test_invalid_dob_future(client):
    p = {**VALID_PATIENT, "date_of_birth": "12/31/2099", "phone_number": "5550000001"}
    r = client.post("/patients", json=p)
    assert r.status_code == 422


def test_invalid_phone_short(client):
    p = {**VALID_PATIENT, "phone_number": "123", "date_of_birth": "01/01/1985"}
    r = client.post("/patients", json=p)
    assert r.status_code == 422


def test_invalid_state(client):
    p = {**VALID_PATIENT, "state": "ZZ", "phone_number": "5550000002"}
    r = client.post("/patients", json=p)
    assert r.status_code == 422


def test_invalid_zip(client):
    p = {**VALID_PATIENT, "zip_code": "123", "phone_number": "5550000003"}
    r = client.post("/patients", json=p)
    assert r.status_code == 422


def test_missing_required_field(client):
    p = {k: v for k, v in VALID_PATIENT.items() if k != "first_name"}
    r = client.post("/patients", json=p)
    assert r.status_code == 422


# ── Query Params ──────────────────────────────────────────────────────────────
def test_search_by_last_name(client):
    client.post("/patients", json=VALID_PATIENT)
    r = client.get("/patients?last_name=User")
    assert r.status_code == 200
    assert len(r.get_json()["data"]) >= 1


def test_search_by_phone(client):
    client.post("/patients", json=VALID_PATIENT)
    r = client.get("/patients?phone_number=5551234567")
    assert r.status_code == 200
    assert len(r.get_json()["data"]) >= 1


# ── Vapi Webhook ──────────────────────────────────────────────────────────────
def test_vapi_assistant_request(client):
    r = client.post("/webhook", json={
        "message": {"type": "assistant-request", "call": {"id": "test-001"}}
    })
    assert r.status_code == 200
    data = r.get_json()
    assert "assistant" in data
    assert data["assistant"]["name"] == "CareCloud-agent"


def test_vapi_end_of_call(client):
    r = client.post("/webhook", json={
        "message": {
            "type": "end-of-call-report",
            "call": {"id": "test-002"},
            "summary": "Patient registered successfully.",
            "transcript": "Alex: Hello..."
        }
    })
    assert r.status_code == 200


def test_vapi_function_call_lookup_notfound(client):
    r = client.post("/webhook", json={
        "message": {
            "type": "function-call",
            "call": {"id": "test-003"},
            "functionCall": {
                "name": "lookup_patient_by_phone",
                "parameters": {"phone_number": "5559999999"}
            }
        }
    })
    assert r.status_code == 200
    result = r.get_json()["result"]
    assert result["found"] is False
