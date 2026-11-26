from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SymptomAnalysisFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "no_symptoms",
        "symptom_frequency",
        "severity_summary",
        "category_distribution",
        "recurring_categories",
        "recurring_descriptions",
        "severity_increase",
        "severity_decrease",
        "severity_stable",
        "trend_insufficient_data",
    ]
    finding_type: Literal["observed_fact", "interpretation"]
    summary: str = Field(min_length=1, max_length=500)
    supporting_metrics: dict[str, int | float | str] = Field(default_factory=dict, max_length=12)
    evidence_references: list[str] = Field(min_length=1, max_length=12)


class SymptomAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_status: Literal["complete", "empty", "insufficient_data"]
    key_findings: list[SymptomAnalysisFinding] = Field(max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    concise_explanation: str = Field(max_length=1000)
