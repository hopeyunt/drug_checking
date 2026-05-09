import uuid
import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> str:
    payload = {
        "email": f"pat_{uuid.uuid4().hex[:8]}@example.com",
        "password": "testpassword123",
        "full_name": "Тест Пациент",
    }
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": payload["email"], "password": payload["password"]},
    )
    return resp.json()["access_token"]


PATIENT_PAYLOAD = {
    "name": "Иванов Иван Иванович",
    "age": 65,
    "weight_kg": 80.0,
    "gfr": 45.0,
    "diagnoses": ["I10", "E11.9"],
    "notes": "Тестовый пациент",
}


@pytest.mark.asyncio
async def test_create_patient(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/patients",
        json=PATIENT_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == PATIENT_PAYLOAD["name"]
    assert data["age"] == PATIENT_PAYLOAD["age"]
    assert data["gfr"] == PATIENT_PAYLOAD["gfr"]
    assert "I10" in data["diagnoses"]


@pytest.mark.asyncio
async def test_create_patient_minimal(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/patients",
        json={"name": "Минимальный Пациент"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["gfr"] is None


@pytest.mark.asyncio
async def test_list_patients_empty(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.get(
        "/api/v1/patients",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_patients(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/api/v1/patients", json=PATIENT_PAYLOAD, headers=headers)
    await client.post("/api/v1/patients", json={**PATIENT_PAYLOAD, "name": "Петров Пётр"}, headers=headers)
    resp = await client.get("/api/v1/patients", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_get_patient(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post("/api/v1/patients", json=PATIENT_PAYLOAD, headers=headers)
    patient_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/patients/{patient_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == patient_id


@pytest.mark.asyncio
async def test_get_patient_not_found(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.get(
        "/api/v1/patients/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_patient(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post("/api/v1/patients", json=PATIENT_PAYLOAD, headers=headers)
    patient_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/v1/patients/{patient_id}",
        json={"age": 70, "notes": "Обновлено"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["age"] == 70
    assert resp.json()["notes"] == "Обновлено"


@pytest.mark.asyncio
async def test_update_patient_not_found(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.patch(
        "/api/v1/patients/99999",
        json={"age": 70},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_patient(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post("/api/v1/patients", json=PATIENT_PAYLOAD, headers=headers)
    patient_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/patients/{patient_id}", headers=headers)
    assert resp.status_code == 204
    resp = await client.get(f"/api/v1/patients/{patient_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_patient_not_found(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.delete(
        "/api/v1/patients/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_renal_risk_normal(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post("/api/v1/patients", json={**PATIENT_PAYLOAD, "gfr": 90.0}, headers=headers)
    patient_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/patients/{patient_id}/renal-risk", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["renal_risk"] == "normal"


@pytest.mark.asyncio
async def test_renal_risk_mild(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post("/api/v1/patients", json={**PATIENT_PAYLOAD, "gfr": 50.0}, headers=headers)
    patient_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/patients/{patient_id}/renal-risk", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["renal_risk"] == "mild"


@pytest.mark.asyncio
async def test_renal_risk_moderate(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post("/api/v1/patients", json={**PATIENT_PAYLOAD, "gfr": 35.0}, headers=headers)
    patient_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/patients/{patient_id}/renal-risk", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["renal_risk"] == "moderate"


@pytest.mark.asyncio
async def test_renal_risk_severe(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post("/api/v1/patients", json={**PATIENT_PAYLOAD, "gfr": 20.0}, headers=headers)
    patient_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/patients/{patient_id}/renal-risk", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["renal_risk"] == "severe"


@pytest.mark.asyncio
async def test_renal_risk_failure(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post("/api/v1/patients", json={**PATIENT_PAYLOAD, "gfr": 5.0}, headers=headers)
    patient_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/patients/{patient_id}/renal-risk", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["renal_risk"] == "failure"


@pytest.mark.asyncio
async def test_renal_risk_no_gfr(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post("/api/v1/patients", json={"name": "Без СКФ"}, headers=headers)
    patient_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/patients/{patient_id}/renal-risk", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["renal_risk"] == "normal"


@pytest.mark.asyncio
async def test_renal_risk_not_found(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.get(
        "/api/v1/patients/99999/renal-risk",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patient_unauthorized(client: AsyncClient):
    resp = await client.post("/api/v1/patients", json=PATIENT_PAYLOAD)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_patient_isolation(client: AsyncClient):
    token1 = await _register_and_login(client)
    token2 = await _register_and_login(client)
    create_resp = await client.post(
        "/api/v1/patients",
        json=PATIENT_PAYLOAD,
        headers={"Authorization": f"Bearer {token1}"},
    )
    patient_id = create_resp.json()["id"]
    resp = await client.get(
        f"/api/v1/patients/{patient_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 404
