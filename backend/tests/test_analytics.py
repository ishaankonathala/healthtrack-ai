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
    test_db_path = tmp_path / "test_analytics.db"
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


def _post_symptom(
    client: TestClient,
    patient_id: str,
    description: str,
    severity: int,
    timestamp: datetime,
) -> None:
    resp = client.post(
        "/symptoms",
        json={
            "patient_id": patient_id,
            "symptom_description": description,
            "severity": severity,
            "timestamp": timestamp.isoformat(),
        },
    )
    assert resp.status_code == 201


def test_analytics_empty_patient_history(client: TestClient):
    resp = client.get("/analytics/patient-empty")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "patient_id": "patient-empty",
        "window_days": 30,
        "total_entries": 0,
        "average_severity": None,
        "highest_severity": None,
        "daily_trend": [],
    }


def test_analytics_totals_average_max_and_daily_grouping(client: TestClient):
    now = datetime.now(timezone.utc)
    day_older = (now - timedelta(days=5)).replace(hour=10, minute=0, second=0, microsecond=0)
    day_middle = (now - timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
    day_latest = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if day_latest > now:
        day_latest = now - timedelta(minutes=5)

    # Insert out of chronological order, with multiple entries on day_middle
    _post_symptom(client, "patient-001", "Evening headache", 8, day_latest)
    _post_symptom(client, "patient-001", "Morning fatigue", 4, day_middle)
    _post_symptom(client, "patient-001", "Afternoon fatigue", 6, day_middle + timedelta(hours=3))
    _post_symptom(client, "patient-001", "Initial sore throat", 2, day_older)

    resp = client.get("/analytics/patient-001")
    assert resp.status_code == 200
    data = resp.json()

    assert data["patient_id"] == "patient-001"
    assert data["total_entries"] == 4
    assert data["average_severity"] == 5.0
    assert data["highest_severity"] == 8

    trend = data["daily_trend"]
    assert len(trend) == 3

    dates = [point["date"] for point in trend]
    assert dates == sorted(dates)
    assert dates == [
        day_older.date().isoformat(),
        day_middle.date().isoformat(),
        day_latest.date().isoformat(),
    ]

    assert trend[0]["average_severity"] == 2.0
    assert trend[0]["entry_count"] == 1
    assert trend[1]["average_severity"] == 5.0
    assert trend[1]["entry_count"] == 2
    assert trend[2]["average_severity"] == 8.0
    assert trend[2]["entry_count"] == 1


def test_analytics_excludes_records_older_than_30_days(client: TestClient):
    now = datetime.now(timezone.utc)
    within_window = now - timedelta(days=10)
    just_inside_window = now - timedelta(days=29, hours=23)
    outside_window_31 = now - timedelta(days=31)
    outside_window_60 = now - timedelta(days=60)

    _post_symptom(client, "patient-window", "Old record 60d", 10, outside_window_60)
    _post_symptom(client, "patient-window", "Old record 31d", 9, outside_window_31)
    _post_symptom(client, "patient-window", "Recent 29d", 3, just_inside_window)
    _post_symptom(client, "patient-window", "Recent 10d", 5, within_window)

    resp = client.get("/analytics/patient-window")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_entries"] == 2
    assert data["average_severity"] == 4.0
    assert data["highest_severity"] == 5
    assert len(data["daily_trend"]) == 2


def test_analytics_patient_specific_isolation(client: TestClient):
    now = datetime.now(timezone.utc) - timedelta(days=1)
    _post_symptom(client, "patient-a", "Symptom A", 3, now)
    _post_symptom(client, "patient-b", "Symptom B", 9, now)

    resp_a = client.get("/analytics/patient-a")
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert data_a["total_entries"] == 1
    assert data_a["average_severity"] == 3.0
    assert data_a["highest_severity"] == 3


def test_analytics_omits_dates_without_entries_never_zero(client: TestClient):
    now = datetime.now(timezone.utc)
    day_1 = now - timedelta(days=15)
    day_2 = now - timedelta(days=3)

    _post_symptom(client, "patient-gaps", "Day 1 symptom", 4, day_1)
    _post_symptom(client, "patient-gaps", "Day 2 symptom", 6, day_2)

    resp = client.get("/analytics/patient-gaps")
    assert resp.status_code == 200
    trend = resp.json()["daily_trend"]

    # Only the 2 dates with entries should be present; gaps are omitted, not 0
    assert len(trend) == 2
    assert all(point["average_severity"] > 0 for point in trend)
    assert all(point["entry_count"] > 0 for point in trend)
