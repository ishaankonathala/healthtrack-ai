from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base
from backend.app.symptom_categories import SYMPTOM_CATEGORY_SQL_VALUES


class SymptomLog(Base):
    """Database model for a patient's logged symptom entry."""

    __tablename__ = "symptom_logs"
    __table_args__ = (
        CheckConstraint("severity >= 1 AND severity <= 10", name="ck_symptom_logs_severity_range"),
        CheckConstraint(
            f"category IS NULL OR category IN ({SYMPTOM_CATEGORY_SQL_VALUES})",
            name="ck_symptom_logs_category",
        ),
        Index("ix_symptom_logs_patient_timestamp", "patient_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symptom_description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    possible_triggers: Mapped[str | None] = mapped_column(Text, nullable=True)


class DailyMoodSleepRecord(Base):
    """One combined mood and sleep check-in per patient per UTC calendar day."""

    __tablename__ = "daily_mood_sleep_records"
    __table_args__ = (
        CheckConstraint("mood_rating >= 1 AND mood_rating <= 5", name="ck_mood_sleep_mood_rating_range"),
        CheckConstraint("sleep_quality >= 1 AND sleep_quality <= 5", name="ck_mood_sleep_quality_range"),
        CheckConstraint(
            "sleep_duration_hours >= 0 AND sleep_duration_hours <= 24",
            name="ck_mood_sleep_duration_range",
        ),
        UniqueConstraint("patient_id", "record_date", name="uq_mood_sleep_patient_record_date"),
        Index("ix_mood_sleep_patient_date", "patient_id", "record_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    mood_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    mood_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mood_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sleep_duration_hours: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    sleep_quality: Mapped[int] = mapped_column(Integer, nullable=False)
    sleep_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
