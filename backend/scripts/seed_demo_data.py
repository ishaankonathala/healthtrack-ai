"""Insert deterministic, clearly synthetic demo records for DEMO-001.

Run from the repository root with:
    .venv/bin/python -m backend.scripts.seed_demo_data

The script only inserts missing records. Existing rows are never updated or deleted.
"""

from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import inspect, select

from backend.app.database import SessionLocal, engine
from backend.app.models import DailyMoodSleepRecord, SymptomLog

PATIENT_ID = "DEMO-001"
DATE_FROM = date(2026, 10, 28)
DATE_TO = date(2026, 11, 26)
SYNTHETIC_PREFIX = "Synthetic demo:"

# date, time, description, severity, category, optional note, optional reported trigger
SYMPTOM_ROWS = (
    ("2026-10-28", "08:20", "mild head pressure during the afternoon", 3, "Headache / Neurological", "Synthetic demo note: brief and manageable.", "patient-reported: extended screen time; not medically verified"),
    ("2026-10-29", "13:10", "shoulder tightness after desk work", 4, "Musculoskeletal", None, "patient-reported: long period at a desk; not medically verified"),
    ("2026-10-31", "17:35", "mild stomach discomfort after a meal", 3, "Digestive", "Synthetic demo note: resolved later that day.", "patient-reported: meal timing; not medically verified"),
    ("2026-11-01", "09:05", "mild head pressure during the afternoon", 4, "Headache / Neurological", None, "patient-reported: extended screen time; not medically verified"),
    ("2026-11-01", "18:15", "dry skin on hands", 2, "Skin", "Synthetic demo note: mild and localized.", None),
    ("2026-11-02", "11:40", "shoulder tightness after desk work", 3, "Musculoskeletal", None, "patient-reported: long period at a desk; not medically verified"),
    ("2026-11-04", "14:25", "mild head pressure during the afternoon", 5, "Headache / Neurological", "Synthetic demo note: more noticeable than the prior entry.", "patient-reported: busy day; not medically verified"),
    ("2026-11-05", "08:45", "felt lower energy than usual", 3, None, "Synthetic demo note: no other detail added.", "patient-reported: shorter sleep the night before; not medically verified"),
    ("2026-11-07", "19:10", "mild stomach discomfort after a meal", 2, "Digestive", None, None),
    ("2026-11-08", "10:30", "mild head pressure during the afternoon", 4, "Headache / Neurological", None, "patient-reported: extended screen time; not medically verified"),
    ("2026-11-08", "16:50", "shoulder tightness after desk work", 5, "Musculoskeletal", "Synthetic demo note: eased after taking a break.", "patient-reported: long period at a desk; not medically verified"),
    ("2026-11-09", "12:15", "scratchy throat noted in the morning", 2, "Respiratory", None, None),
    ("2026-11-11", "15:40", "dry skin on hands", 3, "Skin", None, "patient-reported: frequent hand washing; not medically verified"),
    ("2026-11-12", "09:20", "shoulder tightness after desk work", 4, "Musculoskeletal", None, "patient-reported: long period at a desk; not medically verified"),
    ("2026-11-13", "18:05", "mild head pressure during the afternoon", 3, "Headache / Neurological", "Synthetic demo note: did not interrupt usual activities.", None),
    ("2026-11-14", "13:35", "mild stomach discomfort after a meal", 4, "Digestive", None, "patient-reported: meal timing; not medically verified"),
    ("2026-11-14", "20:10", "felt lower energy than usual", 2, None, None, None),
    ("2026-11-16", "10:00", "shoulder tightness after desk work", 3, "Musculoskeletal", "Synthetic demo note: brief entry.", None),
    ("2026-11-18", "14:55", "mild head pressure during the afternoon", 6, "Headache / Neurological", None, "patient-reported: busy day; not medically verified"),
    ("2026-11-19", "08:35", "mild stomach discomfort after a meal", 3, "Digestive", None, None),
    ("2026-11-20", "11:25", "mild head pressure during the afternoon", 4, "Headache / Neurological", None, "patient-reported: extended screen time; not medically verified"),
    ("2026-11-20", "19:30", "dry skin on hands", 2, "Skin", None, "patient-reported: frequent hand washing; not medically verified"),
    ("2026-11-21", "15:15", "shoulder tightness after desk work", 5, "Musculoskeletal", "Synthetic demo note: more noticeable after a long workday.", "patient-reported: long period at a desk; not medically verified"),
    ("2026-11-23", "09:50", "scratchy throat noted in the morning", 3, "Respiratory", None, None),
    ("2026-11-24", "17:20", "felt lower energy than usual", 4, None, "Synthetic demo note: no additional detail.", None),
    ("2026-11-25", "12:40", "mild head pressure during the afternoon", 5, "Headache / Neurological", None, "patient-reported: extended screen time; not medically verified"),
    ("2026-11-26", "16:05", "shoulder tightness after desk work", 4, "Musculoskeletal", None, "patient-reported: long period at a desk; not medically verified"),
)

# date, mood rating, mood label, sleep hours, sleep quality
MOOD_SLEEP_ROWS = (
    ("2026-10-28", 4, "Good", 7.50, 4),
    ("2026-10-29", 3, "Neutral", 6.50, 3),
    ("2026-10-31", 4, "Good", 7.25, 4),
    ("2026-11-01", 3, "Neutral", 6.00, 3),
    ("2026-11-02", 4, "Good", 7.75, 4),
    ("2026-11-04", 3, "Neutral", 6.25, 3),
    ("2026-11-05", 3, "Neutral", 5.75, 3),
    ("2026-11-07", 4, "Good", 7.50, 4),
    ("2026-11-08", 3, "Neutral", 6.50, 3),
    ("2026-11-09", 4, "Good", 8.00, 4),
    ("2026-11-11", 4, "Good", 7.00, 4),
    ("2026-11-12", 3, "Neutral", 6.00, 3),
    ("2026-11-13", 4, "Good", 7.50, 4),
    ("2026-11-14", 4, "Good", 8.25, 4),
    ("2026-11-16", 3, "Neutral", 6.25, 3),
    ("2026-11-18", 4, "Good", 7.75, 4),
    ("2026-11-19", 3, "Neutral", 5.50, 3),
    ("2026-11-20", 4, "Good", 7.50, 4),
    ("2026-11-21", 3, "Neutral", 6.50, 3),
    ("2026-11-23", 4, "Good", 8.25, 4),
    ("2026-11-25", 4, "Good", 7.00, 4),
    ("2026-11-26", 3, "Neutral", 6.25, 3),
)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def seed_demo_data() -> tuple[int, int, int, int]:
    """Insert missing demo rows and return inserted/skipped symptom and check-in counts."""
    if engine.url.get_backend_name() != "sqlite" or engine.url.database in (None, ":memory:"):
        raise RuntimeError("Demo seeding is restricted to a configured local SQLite database.")
    inspector = inspect(engine)
    if not inspector.has_table(SymptomLog.__tablename__) or not inspector.has_table(DailyMoodSleepRecord.__tablename__):
        raise RuntimeError("Database tables are missing; initialize the application database before seeding.")

    with SessionLocal() as db:
        existing_symptoms = db.scalars(
            select(SymptomLog).where(
                SymptomLog.patient_id == PATIENT_ID,
                SymptomLog.timestamp >= datetime.combine(DATE_FROM, time.min, tzinfo=timezone.utc),
                SymptomLog.timestamp < datetime.combine(date(2026, 11, 27), time.min, tzinfo=timezone.utc),
            )
        ).all()
        existing_symptom_keys = {
            (_as_utc(row.timestamp), row.symptom_description)
            for row in existing_symptoms
        }

        existing_records = db.scalars(
            select(DailyMoodSleepRecord).where(
                DailyMoodSleepRecord.patient_id == PATIENT_ID,
                DailyMoodSleepRecord.record_date >= DATE_FROM,
                DailyMoodSleepRecord.record_date <= DATE_TO,
            )
        ).all()
        existing_record_dates = {row.record_date for row in existing_records}

        new_symptoms = []
        for index, (day_text, time_text, description, severity, category, notes, trigger) in enumerate(SYMPTOM_ROWS):
            day = date.fromisoformat(day_text)
            hour, minute = (int(part) for part in time_text.split(":"))
            timestamp = datetime.combine(day, time(hour, minute), tzinfo=timezone.utc)
            full_description = f"{SYNTHETIC_PREFIX} {description}"
            key = (timestamp, full_description)
            if key in existing_symptom_keys:
                continue
            new_symptoms.append(SymptomLog(
                patient_id=PATIENT_ID,
                symptom_description=full_description,
                severity=severity,
                timestamp=timestamp,
                category=category,
                notes=notes,
                possible_triggers=trigger,
            ))
            existing_symptom_keys.add(key)

        new_checkins = []
        for day_text, mood, label, sleep_hours, quality in MOOD_SLEEP_ROWS:
            record_day = date.fromisoformat(day_text)
            if record_day in existing_record_dates:
                continue
            new_checkins.append(DailyMoodSleepRecord(
                patient_id=PATIENT_ID,
                record_date=record_day,
                mood_rating=mood,
                mood_label=label,
                mood_notes=f"{SYNTHETIC_PREFIX} self-reported mood check-in.",
                sleep_duration_hours=Decimal(str(sleep_hours)),
                sleep_quality=quality,
                sleep_notes=f"{SYNTHETIC_PREFIX} self-reported sleep check-in.",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))
            existing_record_dates.add(record_day)

        db.add_all(new_symptoms + new_checkins)
        db.commit()
        return len(new_symptoms), len(SYMPTOM_ROWS) - len(new_symptoms), len(new_checkins), len(MOOD_SLEEP_ROWS) - len(new_checkins)


def main() -> None:
    inserted_symptoms, skipped_symptoms, inserted_checkins, skipped_checkins = seed_demo_data()
    print(f"patient_id={PATIENT_ID}")
    print(f"date_range_utc={DATE_FROM.isoformat()}..{DATE_TO.isoformat()}")
    print(f"symptom_rows_inserted={inserted_symptoms} already_present_skipped={skipped_symptoms}")
    print(f"mood_sleep_rows_inserted={inserted_checkins} existing_dates_skipped={skipped_checkins}")


if __name__ == "__main__":
    main()
