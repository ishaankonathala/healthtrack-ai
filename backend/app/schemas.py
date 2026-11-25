from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SymptomCreate(BaseModel):
    """Request schema for creating a symptom log."""

    patient_id: str = Field(..., max_length=100, description="Unique identifier for the patient")
    symptom_description: str = Field(
        ...,
        max_length=2000,
        description="Non-empty description of the symptom",
    )
    severity: int = Field(..., ge=1, le=10, description="Symptom severity on a 1 to 10 scale")
    timestamp: datetime | None = Field(
        default=None,
        description="Optional ISO-8601 timestamp; defaults to current UTC time if omitted",
    )

    @field_validator("patient_id", "symptom_description")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace-only")
        return stripped

    def resolved_timestamp(self) -> datetime:
        """Return the provided timestamp or the current UTC datetime."""
        return self.timestamp if self.timestamp is not None else datetime.now(timezone.utc)


class SymptomResponse(BaseModel):
    """Response schema representing a stored symptom log."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: str
    symptom_description: str
    severity: int
    timestamp: datetime


class DailySeverityPoint(BaseModel):
    """Daily aggregated severity metric for a single calendar date."""

    date: str
    average_severity: float
    entry_count: int


class AnalyticsResponse(BaseModel):
    """Response schema for 30-day patient symptom analytics."""

    patient_id: str
    window_days: int = 30
    total_entries: int
    average_severity: float | None
    highest_severity: int | None
    daily_trend: list[DailySeverityPoint]


class AISummaryResponse(BaseModel):
    """Response schema for an AI-generated doctor-visit summary."""

    patient_id: str
    entry_count: int
    model: str
    summary: str
    disclaimer: str


class RAGAskRequest(BaseModel):
    """Request schema for asking the RAG health education assistant."""

    question: str = Field(
        ...,
        max_length=1000,
        description="Non-empty health education question",
    )

    @field_validator("question")
    @classmethod
    def validate_question_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Question must not be empty or whitespace-only")
        return stripped


class RAGSource(BaseModel):
    """Citation metadata for a retrieved health education document."""

    title: str
    url: str


class RAGAskResponse(BaseModel):
    """Response schema for the RAG health education assistant."""

    question: str
    answer: str
    sources: list[RAGSource]
