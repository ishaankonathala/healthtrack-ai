import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import main as main_module
from backend.app.database import Base, get_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'advanced_analytics.db'}", connect_args={"check_same_thread": False})
    sessions = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(main_module, "engine", engine)

    def override_get_db():
        db = sessions()
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
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _symptom(client: TestClient, patient: str, day: str, description: str, severity: int, category: str | None = None) -> dict:
    payload = {
        "patient_id": patient, "timestamp": f"{day}T12:00:00+00:00",
        "symptom_description": description, "severity": severity,
    }
    if category is not None:
        payload["category"] = category
    response = client.post("/symptoms", json=payload)
    assert response.status_code == 201
    return response.json()


def _advanced(client: TestClient, patient: str, start: str, end: str, interval: str = "daily"):
    return client.get(f"/analytics/{patient}/advanced", params={
        "date_from": start, "date_to": end, "interval": interval,
    })


def test_advanced_date_boundaries_categories_and_recurring_patterns(client: TestClient):
    patient = "advanced-boundary"
    _symptom(client, patient, "2025-01-05", " Headache   after work ", 4, "Headache / Neurological")
    _symptom(client, patient, "2025-01-06", "headache after work", 6, "Headache / Neurological")
    _symptom(client, patient, "2025-01-07", "HEADACHE AFTER WORK", 8, "Headache / Neurological")
    legacy = _symptom(client, patient, "2025-01-08", "other symptom", 2)
    assert client.patch(f"/symptoms/{patient}/{legacy['id']}", json={"category": None}).status_code == 200
    _symptom(client, patient, "2025-01-04", "outside start", 10, "Fever")
    _symptom(client, patient, "2025-01-09", "outside end", 10, "Fever")

    result = _advanced(client, patient, "2025-01-05", "2025-01-08").json()
    assert result["total_entries"] == 4
    assert result["average_severity"] == 5.0
    assert result["maximum_severity"] == 8
    categories = {row["category"]: row for row in result["category_frequency"]}
    assert categories["Headache / Neurological"] == {
        "category": "Headache / Neurological", "entry_count": 3, "average_severity": 6.0,
    }
    assert categories["Uncategorized"]["entry_count"] == 1
    description = next(row for row in result["recurring_patterns"] if row["pattern_type"] == "description")
    assert description["occurrence_count"] == 3
    assert description["distinct_dates"] == ["2025-01-05", "2025-01-06", "2025-01-07"]


@pytest.mark.parametrize(("interval", "dates"), [
    ("daily", ["2025-01-05", "2025-01-06", "2025-01-07"]),
    ("weekly", ["2024-12-30", "2025-01-06"]),
    ("monthly", ["2025-01-01"]),
])
def test_advanced_interval_bucket_definitions(client: TestClient, interval: str, dates: list[str]):
    for day in ("2025-01-05", "2025-01-06", "2025-01-07"):
        _symptom(client, "bucket-patient", day, "pain", 3)
    response = _advanced(client, "bucket-patient", "2025-01-05", "2025-01-07", interval)
    assert response.status_code == 200
    assert [point["period_start"] for point in response.json()["trend"]] == dates


def test_advanced_mood_sleep_comparisons_only_use_matching_utc_dates(client: TestClient):
    _symptom(client, "aligned", "2025-02-01", "one", 4)
    _symptom(client, "aligned", "2025-02-01", "two", 6)
    _symptom(client, "aligned", "2025-02-02", "three", 8)
    client.post("/mood-sleep", json={
        "patient_id": "aligned", "record_date": "2025-02-01", "mood_rating": 2,
        "sleep_duration_hours": 5.5, "sleep_quality": 2,
    })
    client.post("/mood-sleep", json={
        "patient_id": "aligned", "record_date": "2025-02-03", "mood_rating": 5,
        "sleep_duration_hours": 8, "sleep_quality": 4,
    })
    result = _advanced(client, "aligned", "2025-02-01", "2025-02-03").json()
    assert result["severity_by_mood_rating"] == [{
        "group": "2 / 5", "average_severity": 5.0, "matching_symptom_entries": 2,
    }]
    assert result["severity_by_sleep_duration"] == [{
        "group": "Under 6 hours", "average_severity": 5.0, "matching_symptom_entries": 2,
    }]


def test_advanced_recurring_threshold_is_three_distinct_dates(client: TestClient):
    for day in ("2025-03-01", "2025-03-01", "2025-03-02"):
        _symptom(client, "threshold", day, "Repeated phrase", 4, "Fever")
    result = _advanced(client, "threshold", "2025-03-01", "2025-03-03").json()
    assert result["recurring_patterns"] == []


def test_advanced_patient_isolation_empty_and_original_contract_unchanged(client: TestClient):
    _symptom(client, "only-patient", "2025-04-01", "headache", 5, "Headache / Neurological")
    advanced = _advanced(client, "no-records", "2025-04-01", "2025-04-30").json()
    assert advanced["total_entries"] == 0
    assert advanced["category_frequency"] == []
    assert advanced["trend"] == []
    original = client.get("/analytics/no-records")
    assert original.status_code == 200
    assert set(original.json()) == {
        "patient_id", "window_days", "total_entries", "average_severity", "highest_severity", "daily_trend",
    }
    assert original.json()["window_days"] == 30


def test_advanced_rejects_invalid_ranges_and_interval(client: TestClient):
    assert _advanced(client, "x", "2025-05-02", "2025-05-01").status_code == 422
    assert client.get("/analytics/x/advanced", params={"interval": "yearly"}).status_code == 422
