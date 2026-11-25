from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import main as main_module
from backend.app.database import Base, get_db
from backend.app.services import ai_service


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Provide a TestClient backed by an isolated temporary SQLite database."""
    test_db_path = tmp_path / "test_ai.db"
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


def test_ai_summary_empty_patient_history(client: TestClient, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-fake-key")
    resp = client.post("/ai/summary/patient-no-records")
    assert resp.status_code == 404
    assert "No symptom records found" in resp.json()["detail"]


def test_ai_summary_missing_api_key(client: TestClient, monkeypatch):
    now = datetime.now(timezone.utc)
    _post_symptom(client, "patient-nokey", "Mild headache", 4, now)

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    resp = client.post("/ai/summary/patient-nokey")
    assert resp.status_code == 503
    assert "GEMINI_API_KEY" in resp.json()["detail"]


def test_ai_summary_generation_with_mocked_llm_and_default_model(client: TestClient, monkeypatch):
    now = datetime.now(timezone.utc)
    _post_symptom(client, "patient-001", "Morning headache", 4, now - timedelta(days=2))
    _post_symptom(client, "patient-001", "Morning headache", 6, now - timedelta(days=1))

    monkeypatch.setenv("GEMINI_API_KEY", "test-fake-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    captured = {}

    def fake_create_llm(api_key: str, model: str):
        captured["api_key"] = api_key
        captured["model"] = model

        def _invoke(prompt_value):
            captured["prompt_text"] = prompt_value.to_string()
            return AIMessage(
                content=(
                    "**Patient & Log Overview**: patient-001 (2 entries)\n"
                    "**Disclaimer**: Not a medical diagnosis."
                )
            )

        return RunnableLambda(_invoke)

    monkeypatch.setattr(ai_service, "create_llm", fake_create_llm)

    resp = client.post("/ai/summary/patient-001")
    assert resp.status_code == 200
    data = resp.json()

    assert captured["model"] == "gemini-3.8-flash"
    assert "patient-001" in captured["prompt_text"]
    assert "Morning headache" in captured["prompt_text"]
    assert data["patient_id"] == "patient-001"
    assert data["entry_count"] == 2
    assert data["model"] == "gemini-3.8-flash"
    assert "patient-001" in data["summary"]
    assert "not a medical diagnosis" in data["disclaimer"].lower()


def test_ai_summary_patient_specific_data_isolation(client: TestClient, monkeypatch):
    now = datetime.now(timezone.utc)
    _post_symptom(client, "patient-alpha", "Dry cough", 3, now - timedelta(days=1))
    _post_symptom(client, "patient-beta", "Severe migraine", 9, now - timedelta(days=1))

    monkeypatch.setenv("GEMINI_API_KEY", "test-fake-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")

    captured_prompts = []

    def fake_create_llm(api_key: str, model: str):
        def _invoke(prompt_value):
            captured_prompts.append(prompt_value.to_string())
            return AIMessage(content="Summary for patient-alpha only. Not a medical diagnosis.")

        return RunnableLambda(_invoke)

    monkeypatch.setattr(ai_service, "create_llm", fake_create_llm)

    resp = client.post("/ai/summary/patient-alpha")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entry_count"] == 1
    assert len(captured_prompts) == 1
    assert "Dry cough" in captured_prompts[0]
    assert "Severe migraine" not in captured_prompts[0]
    assert "patient-beta" not in captured_prompts[0]
