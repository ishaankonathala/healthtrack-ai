from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import main as main_module
from backend.app.database import Base, get_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Provide a TestClient backed by an isolated temporary SQLite database."""
    test_db_path = tmp_path / "test_healthtrack.db"
    test_engine = create_engine(
        f"sqlite:///{test_db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    Base.metadata.create_all(bind=test_engine)
    monkeypatch.setattr(main_module, "engine", test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(main_module.app) as test_client:
            yield test_client
    finally:
        main_module.app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def test_root_and_health_endpoints(client: TestClient):
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert root_resp.json() == {"message": "HealthTrack AI API"}

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json() == {"status": "ok"}


def test_create_symptom_valid(client: TestClient):
    payload = {
        "patient_id": "patient-001",
        "symptom_description": "Mild morning headache",
        "severity": 4,
        "timestamp": "2026-11-20T08:30:00Z",
    }
    response = client.post("/symptoms", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert isinstance(data["id"], int)
    assert data["patient_id"] == "patient-001"
    assert data["symptom_description"] == "Mild morning headache"
    assert data["severity"] == 4
    assert data["timestamp"].startswith("2026-11-20T08:30:00")


def test_create_symptom_default_timestamp(client: TestClient):
    payload = {
        "patient_id": "patient-002",
        "symptom_description": "Fatigue after lunch",
        "severity": 5,
    }
    response = client.post("/symptoms", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["timestamp"] is not None
    parsed_ts = datetime.fromisoformat(data["timestamp"])
    assert isinstance(parsed_ts, datetime)


def test_get_symptoms_ascending_order_at_least_five(client: TestClient):
    base_time = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
    # Insert 6 records out of chronological order
    offsets_hours = [10, 2, 24, 0, 15, 6]
    for idx, offset in enumerate(offsets_hours):
        ts = base_time + timedelta(hours=offset)
        resp = client.post(
            "/symptoms",
            json={
                "patient_id": "patient-chrono",
                "symptom_description": f"Symptom at offset {offset}h (#{idx})",
                "severity": (idx % 10) + 1,
                "timestamp": ts.isoformat(),
            },
        )
        assert resp.status_code == 201

    get_resp = client.get("/symptoms/patient-chrono")
    assert get_resp.status_code == 200
    records = get_resp.json()
    assert len(records) == 6

    timestamps = [datetime.fromisoformat(r["timestamp"]) for r in records]
    assert timestamps == sorted(timestamps)
    assert records[0]["symptom_description"].startswith("Symptom at offset 0h")
    assert records[-1]["symptom_description"].startswith("Symptom at offset 24h")


def test_patient_specific_retrieval(client: TestClient):
    client.post(
        "/symptoms",
        json={
            "patient_id": "patient-alpha",
            "symptom_description": "Dry cough",
            "severity": 3,
        },
    )
    client.post(
        "/symptoms",
        json={
            "patient_id": "patient-beta",
            "symptom_description": "Sore throat",
            "severity": 6,
        },
    )

    alpha_resp = client.get("/symptoms/patient-alpha")
    assert alpha_resp.status_code == 200
    alpha_data = alpha_resp.json()
    assert len(alpha_data) == 1
    assert alpha_data[0]["patient_id"] == "patient-alpha"
    assert alpha_data[0]["symptom_description"] == "Dry cough"

    unknown_resp = client.get("/symptoms/patient-unknown")
    assert unknown_resp.status_code == 200
    assert unknown_resp.json() == []


@pytest.mark.parametrize("bad_description", ["", "   ", "\t\n  "])
def test_reject_empty_or_whitespace_description(client: TestClient, bad_description: str):
    response = client.post(
        "/symptoms",
        json={
            "patient_id": "patient-001",
            "symptom_description": bad_description,
            "severity": 5,
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("valid_severity", [1, 10])
def test_severity_valid_boundaries(client: TestClient, valid_severity: int):
    response = client.post(
        "/symptoms",
        json={
            "patient_id": "patient-bounds",
            "symptom_description": f"Boundary severity {valid_severity}",
            "severity": valid_severity,
        },
    )
    assert response.status_code == 201
    assert response.json()["severity"] == valid_severity


@pytest.mark.parametrize("invalid_severity", [0, -1, 11, 100])
def test_severity_invalid_boundaries(client: TestClient, invalid_severity: int):
    response = client.post(
        "/symptoms",
        json={
            "patient_id": "patient-bounds",
            "symptom_description": "Invalid severity test",
            "severity": invalid_severity,
        },
    )
    assert response.status_code == 422
