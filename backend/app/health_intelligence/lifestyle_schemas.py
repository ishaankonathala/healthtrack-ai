from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LifestyleDailyRecord(BaseModel):
    """Allowlisted scalar fields from one daily mood/sleep row; excludes notes and labels."""

    model_config = ConfigDict(extra="forbid")

    record_date: date
    mood_rating: int = Field(ge=1, le=5)
    sleep_duration_hours: float = Field(ge=0, le=24)
    sleep_quality: int = Field(ge=1, le=5)


class DailySymptomSeverity(BaseModel):
    date: date
    average_severity: float = Field(ge=1, le=10)
    entry_count: int = Field(ge=1)


class SeverityGroupComparison(BaseModel):
    group: str
    average_severity: float = Field(ge=1, le=10)
    matching_symptom_entries: int = Field(ge=1)


class LifestyleAnalysisInput(BaseModel):
    """Patient/date-scoped inputs, with matching symptom aggregates from existing analytics."""

    model_config = ConfigDict(extra="forbid")

    date_from: date
    date_to: date
    records: list[LifestyleDailyRecord] = Field(max_length=366)
    symptom_daily_trend: list[DailySymptomSeverity] = Field(max_length=366)
    symptom_severity_by_mood: list[SeverityGroupComparison] = Field(max_length=5)
    symptom_severity_by_sleep_duration: list[SeverityGroupComparison] = Field(max_length=4)

    @model_validator(mode="after")
    def validate_scope_and_unique_dates(self):
        if self.date_from > self.date_to or (self.date_to - self.date_from).days > 365:
            raise ValueError("Lifestyle input dates must be ordered and cover at most 366 inclusive days")
        dates = [record.record_date for record in self.records]
        if len(dates) != len(set(dates)):
            raise ValueError("At most one daily lifestyle record is allowed per date")
        if any(day < self.date_from or day > self.date_to for day in dates):
            raise ValueError("Lifestyle records must fall inside the selected date range")
        if any(point.date < self.date_from or point.date > self.date_to for point in self.symptom_daily_trend):
            raise ValueError("Symptom trend evidence must fall inside the selected date range")
        return self


class LifestyleAnalysisFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "no_lifestyle_records",
        "mood_distribution",
        "mood_change_comparison",
        "mood_change_insufficient_data",
        "sleep_duration_summary",
        "sleep_duration_distribution",
        "sleep_quality_distribution",
        "missing_checkins",
        "symptom_severity_by_mood",
        "symptom_severity_by_sleep_duration",
        "symptom_severity_by_sleep_quality",
        "no_matched_symptom_data",
    ]
    finding_type: Literal["observed_fact", "comparison"]
    summary: str = Field(min_length=1, max_length=500)
    supporting_metrics: dict[str, int | float | str] = Field(default_factory=dict, max_length=20)
    evidence_references: list[str] = Field(min_length=1, max_length=20)
    sample_size: int = Field(ge=0)


class LifestyleAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_status: Literal["complete", "empty", "insufficient_data"]
    key_findings: list[LifestyleAnalysisFinding] = Field(max_length=30)
    missing_mood_dates: list[date] = Field(max_length=366)
    missing_sleep_dates: list[date] = Field(max_length=366)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    concise_explanation: str = Field(max_length=1000)
