from sqlalchemy import create_engine, text

from backend.app.migrations.versions.v0001_daily_mood_sleep import upgrade


def test_migration_is_additive_and_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy_healthtrack.db'}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE symptom_logs "
                    "(id INTEGER PRIMARY KEY, symptom_description TEXT NOT NULL)"
                )
            )
            connection.execute(
                text("INSERT INTO symptom_logs (id, symptom_description) VALUES (1, 'existing row')")
            )

            upgrade(connection)
            upgrade(connection)

            table_names = {
                row[0]
                for row in connection.execute(
                    text("SELECT name FROM sqlite_master WHERE type = 'table'")
                )
            }
            assert "symptom_logs" in table_names
            assert "daily_mood_sleep_records" in table_names
            assert connection.execute(text("SELECT COUNT(*) FROM symptom_logs")).scalar_one() == 1
            assert connection.execute(
                text("SELECT symptom_description FROM symptom_logs WHERE id = 1")
            ).scalar_one() == "existing row"
    finally:
        engine.dispose()
