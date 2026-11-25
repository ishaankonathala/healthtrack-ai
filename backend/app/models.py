from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class SymptomLog(Base):
    """Database model for a patient's logged symptom entry."""

    __tablename__ = "symptom_logs"
    __table_args__ = (
        CheckConstraint("severity >= 1 AND severity <= 10", name="ck_symptom_logs_severity_range"),
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
