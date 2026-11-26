"""Add nullable symptom category and patient-reported metadata columns.

Run with ``.venv/bin/python -m backend.app.migrations.versions.v0002_symptom_metadata``.
Existing symptom rows remain unchanged and receive NULL in the new columns.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from backend.app.database import engine
from backend.app.symptom_categories import SYMPTOM_CATEGORY_SQL_VALUES


def upgrade(connection: Connection) -> None:
    inspector = inspect(connection)
    if not inspector.has_table("symptom_logs"):
        raise RuntimeError("Expected existing symptom_logs table; initialize the database before this migration.")

    existing_columns = {column["name"] for column in inspector.get_columns("symptom_logs")}
    if "category" not in existing_columns:
        connection.execute(
            text(
                "ALTER TABLE symptom_logs ADD COLUMN category VARCHAR(50) "
                f"CHECK (category IS NULL OR category IN ({SYMPTOM_CATEGORY_SQL_VALUES}))"
            )
        )
    if "notes" not in existing_columns:
        connection.execute(text("ALTER TABLE symptom_logs ADD COLUMN notes TEXT"))
    if "possible_triggers" not in existing_columns:
        connection.execute(text("ALTER TABLE symptom_logs ADD COLUMN possible_triggers TEXT"))


if __name__ == "__main__":
    with engine.begin() as connection:
        upgrade(connection)
    print("Migration v0002 applied (or already present).")
