from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.health_intelligence.symptom_schemas import SymptomAnalysisResult
from backend.app.health_intelligence.lifestyle_schemas import LifestyleAnalysisResult
from backend.app.symptom_categories import SymptomCategory


class SymptomCreate(BaseModel):
    """Request schema for creating a symptom log."""

    patient_id: str = Field(..., max_length=100, description="Unique identifier for the patient")
    symptom_description: str = Field(
        ...,
        max_length=2000,
        description="Non-empty description of the symptom",
    )
    severity: int = Field(..., ge=1, le=10, description="Symptom severity on a 1 to 10 scale")
    category: SymptomCategory = SymptomCategory.GENERAL_OTHER
    notes: str | None = Field(default=None, max_length=2000)
    possible_triggers: str | None = Field(
        default=None,
        max_length=2000,
        description="Patient-reported possible triggers; not medically verified causes",
    )
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

    @field_validator("notes", "possible_triggers")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    def resolved_timestamp(self) -> datetime:
        """Return the provided timestamp or the current UTC datetime."""
        return self.timestamp if self.timestamp is not None else datetime.now(timezone.utc)


class SymptomUpdate(BaseModel):
    """Partial update for an existing symptom record."""

    symptom_description: str | None = Field(default=None, max_length=2000)
    severity: int | None = Field(default=None, ge=1, le=10)
    category: SymptomCategory | None = None
    notes: str | None = Field(default=None, max_length=2000)
    possible_triggers: str | None = Field(default=None, max_length=2000)
    timestamp: datetime | None = None

    @field_validator("symptom_description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("symptom_description must not be empty or whitespace-only")
        return cleaned

    @field_validator("notes", "possible_triggers")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied for an update")
        for field in ("symptom_description", "severity", "timestamp"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class SymptomResponse(BaseModel):
    """Response schema representing a stored symptom log."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: str
    symptom_description: str
    severity: int
    category: SymptomCategory | None
    notes: str | None
    possible_triggers: str | None
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


class AnalyticsBucket(BaseModel):
    period_start: str
    average_severity: float
    maximum_severity: int
    entry_count: int


class CategoryAnalytics(BaseModel):
    category: str
    entry_count: int
    average_severity: float


class RecurringSymptomPattern(BaseModel):
    pattern_type: str
    label: str
    occurrence_count: int
    distinct_dates: list[str]


class SeverityComparison(BaseModel):
    group: str
    average_severity: float
    matching_symptom_entries: int


class AdvancedAnalyticsResponse(BaseModel):
    patient_id: str
    date_from: date
    date_to: date
    interval: str
    total_entries: int
    average_severity: float | None
    maximum_severity: int | None
    trend: list[AnalyticsBucket]
    category_frequency: list[CategoryAnalytics]
    category_severity: list[CategoryAnalytics]
    recurring_patterns: list[RecurringSymptomPattern]
    severity_by_mood_rating: list[SeverityComparison]
    severity_by_sleep_duration: list[SeverityComparison]


class HealthIntelligenceRequest(BaseModel):
    """Bounded UTC calendar-date range for explicit health-intelligence requests."""

    model_config = ConfigDict(extra="forbid")

    date_from: date
    date_to: date
    educational_question: str | None = Field(default=None, max_length=1000)

    @field_validator("educational_question")
    @classmethod
    def validate_educational_question(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("educational_question must not be blank")
        return cleaned

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.date_from > self.date_to:
            raise ValueError("date_from must be on or before date_to")
        if (self.date_to - self.date_from).days > 365:
            raise ValueError("Date range cannot exceed 366 inclusive calendar days")
        return self


class HealthIntelligenceEvidence(BaseModel):
    """Compact, deterministic evidence prepared for report generation."""

    recorded_facts: list[str]
    analytical_observations: list[str]


class HealthIntelligenceAnalytics(BaseModel):
    """Allowlisted aggregate-only subset; excludes free-text symptom descriptions."""

    total_entries: int
    average_severity: float | None
    maximum_severity: int | None
    trend: list[AnalyticsBucket]
    category_frequency: list[CategoryAnalytics]
    recurring_category_patterns: list[RecurringSymptomPattern]
    recurring_description_pattern_count: int
    severity_by_mood_rating: list[SeverityComparison]
    severity_by_sleep_duration: list[SeverityComparison]


class HealthIntelligenceSource(BaseModel):
    """Attribution returned by the existing curated health-education retriever."""

    title: str
    url: str


class MedicalKnowledgeResult(BaseModel):
    """General educational retrieval kept separate from patient-specific evidence."""

    agent_status: Literal["complete", "no_relevant_information", "unavailable"]
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(max_length=4000)
    sources: list[HealthIntelligenceSource] = Field(default_factory=list, max_length=3)
    warnings: list[str] = Field(default_factory=list, max_length=10)
    limitations: list[str] = Field(default_factory=list, max_length=10)


class HealthIntelligenceReport(BaseModel):
    """Structured health report retaining the original flat fields for compatibility."""

    model_config = ConfigDict(extra="forbid")

    patient_recorded_facts: list[str] = Field(max_length=100)
    deterministic_observations: list[str] = Field(max_length=100)
    general_educational_information: str | None = None
    educational_sources: list[HealthIntelligenceSource] = Field(default_factory=list, max_length=3)
    ai_generated_explanations: list[str] = Field(max_length=6)
    disclaimer: str
    executive_summary: str = Field(default="", max_length=1500)
    symptom_analysis: SymptomAnalysisResult | None = None
    lifestyle_analysis: LifestyleAnalysisResult | None = None
    medical_knowledge_context: MedicalKnowledgeResult | None = None
    warnings: list[str] = Field(default_factory=list, max_length=100)
    limitations: list[str] = Field(default_factory=list, max_length=100)
    ai_explanation_status: Literal["generated", "skipped_no_records", "unavailable"] = "skipped_no_records"
    prototype_notice: str = (
        "HealthTrack AI is a synthetic-data educational prototype, not a clinical decision-support or production healthcare system."
    )


class HealthIntelligenceResponse(BaseModel):
    request_id: str
    patient_id: str
    date_from: date
    date_to: date
    symptom_analysis: SymptomAnalysisResult
    lifestyle_analysis: LifestyleAnalysisResult
    medical_knowledge: MedicalKnowledgeResult | None = None
    report: HealthIntelligenceReport
    warnings: list[str]


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


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class MoodSleepCreate(BaseModel):
    """Create a combined daily mood and sleep check-in."""

    patient_id: str = Field(..., min_length=1, max_length=100)
    record_date: date = Field(default_factory=lambda: datetime.now(timezone.utc).date())
    mood_rating: int = Field(..., ge=1, le=5)
    mood_label: str | None = Field(default=None, max_length=50)
    mood_notes: str | None = Field(default=None, max_length=2000)
    sleep_duration_hours: float = Field(..., ge=0, le=24)
    sleep_quality: int = Field(..., ge=1, le=5)
    sleep_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("patient_id")
    @classmethod
    def validate_patient_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("patient_id must not be empty or whitespace-only")
        return cleaned

    @field_validator("mood_label", "mood_notes", "sleep_notes")
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)


class MoodSleepUpdate(BaseModel):
    """Partial update for a daily mood and sleep check-in."""

    record_date: date | None = None
    mood_rating: int | None = Field(default=None, ge=1, le=5)
    mood_label: str | None = Field(default=None, max_length=50)
    mood_notes: str | None = Field(default=None, max_length=2000)
    sleep_duration_hours: float | None = Field(default=None, ge=0, le=24)
    sleep_quality: int | None = Field(default=None, ge=1, le=5)
    sleep_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("mood_label", "mood_notes", "sleep_notes")
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @model_validator(mode="after")
    def require_at_least_one_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied for an update")
        for field in ("record_date", "mood_rating", "sleep_duration_hours", "sleep_quality"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class MoodSleepResponse(BaseModel):
    """Persistent daily mood and sleep record with UTC audit timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: str
    record_date: date
    mood_rating: int
    mood_label: str | None
    mood_notes: str | None
    sleep_duration_hours: float
    sleep_quality: int
    sleep_notes: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def timestamps_are_utc(cls, value: datetime) -> datetime:
        return _normalize_utc_datetime(value)
