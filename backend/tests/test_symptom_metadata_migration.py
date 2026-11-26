import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from backend.app.migrations.versions.v0002_symptom_metadata import upgrade


def test_symptom_metadata_migration_is_additive_and_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy_symptoms.db'}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE symptom_logs ("
                    "id INTEGER PRIMARY KEY, patient_id VARCHAR(100) NOT NULL, "
                    "symptom_description TEXT NOT NULL, severity INTEGER NOT NULL, timestamp DATETIME NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO symptom_logs (id, patient_id, symptom_description, severity, timestamp) "
                    "VALUES (1, 'patient-a', 'Legacy headache', 4, '2026-11-20 08:00:00'), "
                    "(2, 'patient-b', 'Legacy fatigue', 6, '2026-11-21 09:00:00')"
                )
            )
            before = connection.execute(
                text("SELECT id, patient_id, symptom_description, severity, timestamp FROM symptom_logs ORDER BY id")
            ).all()

            upgrade(connection)
            upgrade(connection)

            after = connection.execute(
                text("SELECT id, patient_id, symptom_description, severity, timestamp FROM symptom_logs ORDER BY id")
            ).all()
            assert after == before
            columns = {column["name"] for column in inspect(connection).get_columns("symptom_logs")}
            assert {"category", "notes", "possible_triggers"}.issubset(columns)
            assert connection.execute(
                text("SELECT COUNT(*) FROM symptom_logs WHERE category IS NULL AND notes IS NULL AND possible_triggers IS NULL")
            ).scalar_one() == 2

            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO symptom_logs "
                        "(id, patient_id, symptom_description, severity, timestamp, category) "
                        "VALUES (3, 'patient-a', 'Invalid category', 2, '2026-11-22 09:00:00', 'Neurology')"
                    )
                )
    finally:
        engine.dispose()
