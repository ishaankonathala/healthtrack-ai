from datetime import date
from typing import Literal, TypedDict

from backend.app.schemas import (
    HealthIntelligenceAnalytics,
    HealthIntelligenceEvidence,
    HealthIntelligenceReport,
    MedicalKnowledgeResult,
)
from backend.app.health_intelligence.symptom_schemas import SymptomAnalysisResult
from backend.app.health_intelligence.lifestyle_schemas import LifestyleAnalysisInput, LifestyleAnalysisResult


class HealthIntelligenceState(TypedDict, total=False):
    """Graph state contains only scoped identifiers, bounded aggregates, and output."""

    patient_id: str
    date_from: date
    date_to: date
    request_id: str
    analytics: HealthIntelligenceAnalytics | None
    symptom_evidence: HealthIntelligenceEvidence | None
    symptom_analysis_result: SymptomAnalysisResult | None
    lifestyle_evidence: HealthIntelligenceEvidence | None
    lifestyle_analysis_input: LifestyleAnalysisInput | None
    lifestyle_analysis_result: LifestyleAnalysisResult | None
    educational_question: str | None
    medical_knowledge_result: MedicalKnowledgeResult | None
    warnings: list[str]
    report: HealthIntelligenceReport | None
    execution_status: Literal["pending", "running", "succeeded", "failed"]
    error_code: str | None
