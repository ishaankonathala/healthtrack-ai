from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app import main as main_module
from backend.app.database import Base, get_db
from backend.app.models import SymptomLog


@pytest.fixture()
def client(tmp_path, monkeypatch):
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'test_symptom_management.db'}",
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


def symptom_payload(**overrides):
    values = {
        "patient_id": "patient-symptom-management",
        "symptom_description": "Intermittent headache",
        "severity": 5,
        "timestamp": "2026-11-20T08:30:00Z",
        "category": "Headache / Neurological",
        "notes": "Started after a long day.",
        "possible_triggers": "Patient suspects lack of sleep.",
    }
    values.update(overrides)
    return values


def test_category_validation_and_legacy_create_payload_compatibility(client: TestClient):
    legacy_payload = symptom_payload()
    legacy_payload.pop("category")
    legacy_payload.pop("notes")
    legacy_payload.pop("possible_triggers")
    response = client.post("/symptoms", json=legacy_payload)
    assert response.status_code == 201
    assert response.json()["category"] == "General / Other"
    assert response.json()["notes"] is None
    assert response.json()["possible_triggers"] is None

    invalid = client.post("/symptoms", json=symptom_payload(category="Neurology"))
    assert invalid.status_code == 422


def test_optional_notes_and_patient_reported_triggers_are_persisted(client: TestClient):
    response = client.post("/symptoms", json=symptom_payload())
    assert response.status_code == 201
    record_id = response.json()["id"]
    loaded = client.get("/symptoms/patient-symptom-management").json()[0]
    assert loaded["notes"] == "Started after a long day."
    assert loaded["possible_triggers"] == "Patient suspects lack of sleep."
    assert loaded["category"] == "Headache / Neurological"
    assert client.get(f"/symptoms/patient-symptom-management?category=uncategorized").json() == []
    assert record_id == loaded["id"]


def test_legacy_row_without_category_is_returned_and_filterable(client: TestClient):
    with Session(main_module.engine) as db:
        record = SymptomLog(
            patient_id="patient-legacy-category",
            symptom_description="Legacy symptom row",
            severity=3,
            timestamp=datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc),
        )
        db.add(record)
        db.commit()
        record_id = record.id

    history = client.get("/symptoms/patient-legacy-category")
    assert history.status_code == 200
    assert history.json()[0]["id"] == record_id
    assert history.json()[0]["category"] is None
    assert history.json()[0]["notes"] is None
    uncategorized = client.get("/symptoms/patient-legacy-category", params={"category": "uncategorized"})
    assert [record["id"] for record in uncategorized.json()] == [record_id]


def test_combined_symptom_history_filters(client: TestClient):
    records = [
        symptom_payload(timestamp="2026-11-20T08:00:00Z", category="Fever", severity=3),
        symptom_payload(timestamp="2026-11-21T09:00:00Z", category="Fever", severity=6),
        symptom_payload(timestamp="2026-11-22T08:00:00Z", category="Respiratory", severity=8),
    ]
    for record in records:
        assert client.post("/symptoms", json=record).status_code == 201
    client.post("/symptoms", json=symptom_payload(patient_id="other-patient", category="Fever", severity=6))

    response = client.get(
        "/symptoms/patient-symptom-management",
        params={
            "category": "Fever",
            "min_severity": 5,
            "max_severity": 7,
            "date_from": "2026-11-20",
            "date_to": "2026-11-21",
        },
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["timestamp"].startswith("2026-11-21T09:00:00")

    assert client.get(
        "/symptoms/patient-symptom-management",
        params={"min_severity": 8, "max_severity": 2},
    ).status_code == 422
    assert client.get(
        "/symptoms/patient-symptom-management",
        params={"date_from": "2026-11-22", "date_to": "2026-11-20"},
    ).status_code == 422


def test_patient_scoped_update_and_delete_and_persistence(client: TestClient):
    created = client.post("/symptoms", json=symptom_payload()).json()
    record_id = created["id"]
    path = f"/symptoms/patient-symptom-management/{record_id}"

    cross_patient_update = client.patch(
        f"/symptoms/another-patient/{record_id}",
        json={"severity": 9},
    )
    assert cross_patient_update.status_code == 404

    updated = client.patch(
        path,
        json={"severity": 7, "category": "Digestive", "notes": "Updated notes", "possible_triggers": None},
    )
    assert updated.status_code == 200
    assert updated.json()["severity"] == 7
    assert updated.json()["category"] == "Digestive"
    assert updated.json()["notes"] == "Updated notes"
    assert updated.json()["possible_triggers"] is None
    assert client.get("/symptoms/patient-symptom-management").json()[0]["id"] == record_id

    assert client.delete(f"/symptoms/another-patient/{record_id}").status_code == 404
    deleted = client.delete(path)
    assert deleted.status_code == 204
    assert client.get("/symptoms/patient-symptom-management").json() == []
    assert client.delete(path).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"severity": None},
        {"symptom_description": "   "},
        {},
    ],
)
def test_invalid_symptom_updates_are_rejected(client: TestClient, payload: dict):
    created = client.post("/symptoms", json=symptom_payload()).json()
    response = client.patch(
        f"/symptoms/patient-symptom-management/{created['id']}",
        json=payload,
    )
    assert response.status_code == 422
