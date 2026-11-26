from datetime import date, datetime, timezone
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import DailyMoodSleepRecord
from backend.app.schemas import MoodSleepCreate, MoodSleepUpdate


class DuplicateDailyRecordError(Exception):
    """A patient already has a check-in for this UTC calendar date."""


class MoodSleepRecordNotFoundError(Exception):
    """The requested record does not exist for the specified patient."""


class MoodSleepAnalysisRow(NamedTuple):
    """Scalar fields needed for deterministic analysis; excludes note and label columns."""

    record_date: date
    mood_rating: int
    sleep_duration_hours: float
    sleep_quality: int


def _commit_or_raise_duplicate(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uq_mood_sleep_patient_record_date" in str(exc).lower() or "unique constraint failed: daily_mood_sleep_records.patient_id, daily_mood_sleep_records.record_date" in str(exc).lower():
            raise DuplicateDailyRecordError from exc
        raise


def create_mood_sleep_record(db: Session, payload: MoodSleepCreate) -> DailyMoodSleepRecord:
    now = datetime.now(timezone.utc)
    values = payload.model_dump()
    values["sleep_duration_hours"] = Decimal(str(payload.sleep_duration_hours))
    record = DailyMoodSleepRecord(
        **values,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    _commit_or_raise_duplicate(db)
    db.refresh(record)
    return record


def get_mood_sleep_history(db: Session, patient_id: str) -> list[DailyMoodSleepRecord]:
    statement = (
        select(DailyMoodSleepRecord)
        .where(DailyMoodSleepRecord.patient_id == patient_id)
        .order_by(DailyMoodSleepRecord.record_date.asc(), DailyMoodSleepRecord.id.asc())
    )
    return list(db.scalars(statement).all())


def get_mood_sleep_analysis_rows(
    db: Session,
    patient_id: str,
    date_from: date,
    date_to: date,
) -> list[MoodSleepAnalysisRow]:
    """Read only bounded analysis columns for one patient; mood/sleep notes are not selected."""
    statement = (
        select(
            DailyMoodSleepRecord.record_date,
            DailyMoodSleepRecord.mood_rating,
            DailyMoodSleepRecord.sleep_duration_hours,
            DailyMoodSleepRecord.sleep_quality,
        )
        .where(
            DailyMoodSleepRecord.patient_id == patient_id,
            DailyMoodSleepRecord.record_date >= date_from,
            DailyMoodSleepRecord.record_date <= date_to,
        )
        .order_by(DailyMoodSleepRecord.record_date.asc(), DailyMoodSleepRecord.id.asc())
    )
    return [
        MoodSleepAnalysisRow(
            record_date=row.record_date,
            mood_rating=row.mood_rating,
            sleep_duration_hours=float(row.sleep_duration_hours),
            sleep_quality=row.sleep_quality,
        )
        for row in db.execute(statement)
    ]


def update_mood_sleep_record(
    db: Session,
    patient_id: str,
    record_id: int,
    changes: MoodSleepUpdate,
) -> DailyMoodSleepRecord:
    record = db.scalar(
        select(DailyMoodSleepRecord).where(
            DailyMoodSleepRecord.id == record_id,
            DailyMoodSleepRecord.patient_id == patient_id,
        )
    )
    if record is None:
        raise MoodSleepRecordNotFoundError

    for field, value in changes.model_dump(exclude_unset=True).items():
        if field == "sleep_duration_hours" and value is not None:
            value = Decimal(str(value))
        setattr(record, field, value)
    record.updated_at = datetime.now(timezone.utc)
    _commit_or_raise_duplicate(db)
    db.refresh(record)
    return record


def delete_mood_sleep_record(db: Session, patient_id: str, record_id: int) -> None:
    record = db.scalar(
        select(DailyMoodSleepRecord).where(
            DailyMoodSleepRecord.id == record_id,
            DailyMoodSleepRecord.patient_id == patient_id,
        )
    )
    if record is None:
        raise MoodSleepRecordNotFoundError
    db.delete(record)
    db.commit()
