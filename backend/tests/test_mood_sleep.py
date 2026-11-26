from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import main as main_module
from backend.app.database import Base, get_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Provide an isolated database for daily mood and sleep API tests."""
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'test_mood_sleep.db'}",
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


def payload(**overrides):
    values = {
        "patient_id": "patient-mood-test",
        "record_date": "2026-11-20",
        "mood_rating": 4,
        "mood_label": "Calm",
        "mood_notes": "Felt steady during the day.",
        "sleep_duration_hours": 7.5,
        "sleep_quality": 4,
        "sleep_notes": "Woke once overnight.",
    }
    values.update(overrides)
    return values


def test_create_mood_sleep_record_and_persist_utc_timestamps(client: TestClient):
    response = client.post("/mood-sleep", json=payload())
    assert response.status_code == 201
    created = response.json()
    assert created["patient_id"] == "patient-mood-test"
    assert created["record_date"] == "2026-11-20"
    assert created["mood_rating"] == 4
    assert created["sleep_duration_hours"] == 7.5
    assert created["sleep_quality"] == 4
    assert datetime.fromisoformat(created["created_at"]).utcoffset().total_seconds() == 0
    assert datetime.fromisoformat(created["updated_at"]).utcoffset().total_seconds() == 0

    # A new request/session reads the persisted record back from the test database.
    history = client.get("/mood-sleep/patient-mood-test")
    assert history.status_code == 200
    assert [record["id"] for record in history.json()] == [created["id"]]


@pytest.mark.parametrize("mood_rating", [0, 6, -1, 100])
def test_reject_invalid_mood_rating(client: TestClient, mood_rating: int):
    assert client.post("/mood-sleep", json=payload(mood_rating=mood_rating)).status_code == 422


@pytest.mark.parametrize("sleep_quality", [0, 6, -1, 100])
def test_reject_invalid_sleep_quality(client: TestClient, sleep_quality: int):
    assert client.post("/mood-sleep", json=payload(sleep_quality=sleep_quality)).status_code == 422


@pytest.mark.parametrize("duration", [-0.01, 24.01, 100])
def test_reject_sleep_duration_out_of_bounds(client: TestClient, duration: float):
    assert client.post("/mood-sleep", json=payload(sleep_duration_hours=duration)).status_code == 422


def test_accept_sleep_duration_boundaries(client: TestClient):
    for day, duration in (("2026-11-21", 0), ("2026-11-22", 24)):
        response = client.post(
            "/mood-sleep",
            json=payload(record_date=day, sleep_duration_hours=duration),
        )
        assert response.status_code == 201


def test_history_is_patient_specific_and_chronological(client: TestClient):
    client.post("/mood-sleep", json=payload(record_date="2026-11-22"))
    client.post("/mood-sleep", json=payload(record_date="2026-11-19"))
    client.post("/mood-sleep", json=payload(patient_id="another-patient", record_date="2026-11-20"))

    response = client.get("/mood-sleep/patient-mood-test")
    assert response.status_code == 200
    records = response.json()
    assert [record["record_date"] for record in records] == ["2026-11-19", "2026-11-22"]
    assert all(record["patient_id"] == "patient-mood-test" for record in records)


def test_duplicate_daily_record_returns_conflict(client: TestClient):
    assert client.post("/mood-sleep", json=payload()).status_code == 201
    duplicate = client.post("/mood-sleep", json=payload(mood_rating=2))
    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]


def test_update_existing_record_and_reject_empty_update(client: TestClient):
    created = client.post("/mood-sleep", json=payload()).json()
    updated = client.patch(
        f"/mood-sleep/patient-mood-test/{created['id']}",
        json={"mood_rating": 2, "mood_label": None, "sleep_duration_hours": 8.25},
    )
    assert updated.status_code == 200
    assert updated.json()["mood_rating"] == 2
    assert updated.json()["mood_label"] is None
    assert updated.json()["sleep_duration_hours"] == 8.25
    assert updated.json()["updated_at"] >= created["updated_at"]
    assert client.patch(f"/mood-sleep/patient-mood-test/{created['id']}", json={}).status_code == 422
    assert client.patch(
        f"/mood-sleep/patient-mood-test/{created['id']}",
        json={"mood_rating": None},
    ).status_code == 422


def test_update_date_collision_returns_conflict(client: TestClient):
    first = client.post("/mood-sleep", json=payload()).json()
    client.post("/mood-sleep", json=payload(record_date="2026-11-21"))
    response = client.patch(
        f"/mood-sleep/patient-mood-test/{first['id']}",
        json={"record_date": "2026-11-21"},
    )
    assert response.status_code == 409


def test_delete_record_and_scope_lookup_to_patient(client: TestClient):
    created = client.post("/mood-sleep", json=payload()).json()
    assert client.delete(f"/mood-sleep/other-patient/{created['id']}").status_code == 404
    deleted = client.delete(f"/mood-sleep/patient-mood-test/{created['id']}")
    assert deleted.status_code == 204
    assert client.get("/mood-sleep/patient-mood-test").json() == []
    assert client.delete(f"/mood-sleep/patient-mood-test/{created['id']}").status_code == 404


def test_missing_or_blank_patient_id_is_rejected(client: TestClient):
    missing = payload()
    missing.pop("patient_id")
    assert client.post("/mood-sleep", json=missing).status_code == 422
    assert client.post("/mood-sleep", json=payload(patient_id="   ")).status_code == 422
    assert client.get("/mood-sleep/%20%20").status_code == 422


def test_create_defaults_record_date_to_current_utc_day(client: TestClient):
    values = payload()
    values.pop("record_date")
    response = client.post("/mood-sleep", json=values)
    assert response.status_code == 201
    assert response.json()["record_date"] == datetime.now(timezone.utc).date().isoformat()
