from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import SymptomLog
from backend.app.schemas import SymptomUpdate
from backend.app.symptom_categories import SymptomCategory


class SymptomRecordNotFoundError(Exception):
    """The record does not exist for the specified patient."""


CategoryFilter = SymptomCategory | Literal["uncategorized"] | None


def get_symptom_history(
    db: Session,
    patient_id: str,
    *,
    category: CategoryFilter = None,
    min_severity: int | None = None,
    max_severity: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[SymptomLog]:
    statement = select(SymptomLog).where(SymptomLog.patient_id == patient_id)
    if category == "uncategorized":
        statement = statement.where(SymptomLog.category.is_(None))
    elif category is not None:
        statement = statement.where(SymptomLog.category == category.value)
    if min_severity is not None:
        statement = statement.where(SymptomLog.severity >= min_severity)
    if max_severity is not None:
        statement = statement.where(SymptomLog.severity <= max_severity)
    if date_from is not None:
        start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        statement = statement.where(SymptomLog.timestamp >= start)
    if date_to is not None:
        end_exclusive = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        statement = statement.where(SymptomLog.timestamp < end_exclusive)
    statement = statement.order_by(SymptomLog.timestamp.asc(), SymptomLog.id.asc())
    return list(db.scalars(statement).all())


def _get_owned_record(db: Session, patient_id: str, record_id: int) -> SymptomLog:
    record = db.scalar(
        select(SymptomLog).where(
            SymptomLog.id == record_id,
            SymptomLog.patient_id == patient_id,
        )
    )
    if record is None:
        raise SymptomRecordNotFoundError
    return record


def update_symptom_record(
    db: Session,
    patient_id: str,
    record_id: int,
    changes: SymptomUpdate,
) -> SymptomLog:
    record = _get_owned_record(db, patient_id, record_id)
    for field, value in changes.model_dump(exclude_unset=True).items():
        if isinstance(value, SymptomCategory):
            value = value.value
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


def delete_symptom_record(db: Session, patient_id: str, record_id: int) -> None:
    record = _get_owned_record(db, patient_id, record_id)
    db.delete(record)
    db.commit()
