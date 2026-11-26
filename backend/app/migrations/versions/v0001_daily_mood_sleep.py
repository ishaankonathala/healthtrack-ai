"""Create the daily mood and sleep table without changing existing tables.

Run with ``.venv/bin/python -m backend.app.migrations.versions.v0001_daily_mood_sleep``.
The DDL is idempotent; no existing symptom data is copied, rewritten, or removed.
"""

from sqlalchemy import text
from sqlalchemy.engine import Connection

from backend.app.database import engine


def upgrade(connection: Connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS daily_mood_sleep_records (
                id INTEGER NOT NULL PRIMARY KEY,
                patient_id VARCHAR(100) NOT NULL,
                record_date DATE NOT NULL,
                mood_rating INTEGER NOT NULL,
                mood_label VARCHAR(50),
                mood_notes TEXT,
                sleep_duration_hours NUMERIC(4, 2) NOT NULL,
                sleep_quality INTEGER NOT NULL,
                sleep_notes TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT ck_mood_sleep_mood_rating_range
                    CHECK (mood_rating >= 1 AND mood_rating <= 5),
                CONSTRAINT ck_mood_sleep_quality_range
                    CHECK (sleep_quality >= 1 AND sleep_quality <= 5),
                CONSTRAINT ck_mood_sleep_duration_range
                    CHECK (sleep_duration_hours >= 0 AND sleep_duration_hours <= 24),
                CONSTRAINT uq_mood_sleep_patient_record_date
                    UNIQUE (patient_id, record_date)
            )
            """
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_mood_sleep_patient_date "
            "ON daily_mood_sleep_records (patient_id, record_date)"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_daily_mood_sleep_records_patient_id "
            "ON daily_mood_sleep_records (patient_id)"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_daily_mood_sleep_records_id "
            "ON daily_mood_sleep_records (id)"
        )
    )


if __name__ == "__main__":
    with engine.begin() as connection:
        upgrade(connection)
    print("Migration v0001 applied (or already present).")
