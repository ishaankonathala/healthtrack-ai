from datetime import date

from sqlalchemy.orm import Session

from backend.app.schemas import (
    AdvancedAnalyticsResponse,
    HealthIntelligenceAnalytics,
    HealthIntelligenceEvidence,
    HealthIntelligenceReport,
)
from backend.app.services.analytics_service import get_advanced_patient_analytics
from backend.app.services.ai_service import create_llm  # compatibility alias; report generation lives in report_agent
from backend.app.health_intelligence.symptom_agent import analyze_symptom_evidence
from backend.app.health_intelligence.lifestyle_agent import analyze_lifestyle_evidence
from backend.app.health_intelligence.lifestyle_schemas import (
    DailySymptomSeverity,
    LifestyleAnalysisInput,
    LifestyleDailyRecord,
    SeverityGroupComparison,
)
from backend.app.health_intelligence.medical_knowledge_agent import (
    MedicalKnowledgeInput,
    analyze_medical_knowledge,
)
from backend.app.services.mood_sleep_service import get_mood_sleep_analysis_rows
from backend.app.health_intelligence.state import HealthIntelligenceState
from backend.app.health_intelligence.report_agent import HealthReportAgentInput, generate_health_report

MAX_RECURRING_CATEGORIES_IN_REPORT = 20


def validate_request(state: HealthIntelligenceState) -> dict:
    patient_value = state.get("patient_id")
    patient_id = patient_value.strip() if isinstance(patient_value, str) else ""
    date_from = state.get("date_from")
    date_to = state.get("date_to")
    educational_question = state.get("educational_question")
    errors = []
    if not patient_id or len(patient_id) > 100:
        errors.append("A non-empty patient ID of at most 100 characters is required.")
    request_id = state.get("request_id")
    if not isinstance(request_id, str) or not request_id or len(request_id) > 100:
        errors.append("A bounded request ID is required.")
    if not isinstance(date_from, date) or not isinstance(date_to, date):
        errors.append("Both date bounds must be valid calendar dates.")
    elif date_from > date_to:
        errors.append("date_from must be on or before date_to.")
    elif (date_to - date_from).days > 365:
        errors.append("Date range cannot exceed 366 inclusive calendar days.")
    if educational_question is not None and (
        not isinstance(educational_question, str)
        or not educational_question.strip()
        or len(educational_question) > 1000
    ):
        errors.append("An optional educational question must contain 1 to 1000 non-whitespace characters.")
    if errors:
        return {"execution_status": "failed", "error_code": "invalid_request", "warnings": errors}
    return {"patient_id": patient_id, "execution_status": "running", "warnings": [], "error_code": None}


def _can_continue(state: HealthIntelligenceState) -> bool:
    return state.get("execution_status") == "running"


def gather_patient_evidence(state: HealthIntelligenceState, *, db: Session) -> dict:
    if not _can_continue(state):
        return {}
    try:
        raw: AdvancedAnalyticsResponse = get_advanced_patient_analytics(
            db=db,
            patient_id=state["patient_id"],
            date_from=state["date_from"],
            date_to=state["date_to"],
            interval="daily",
        )
        mood_sleep_rows = get_mood_sleep_analysis_rows(
            db=db,
            patient_id=state["patient_id"],
            date_from=state["date_from"],
            date_to=state["date_to"],
        )
        recurring_categories = [
            pattern for pattern in raw.recurring_patterns if pattern.pattern_type == "category"
        ][:MAX_RECURRING_CATEGORIES_IN_REPORT]
        omitted = max(
            0,
            sum(pattern.pattern_type == "category" for pattern in raw.recurring_patterns)
            - len(recurring_categories),
        )
        analytics = HealthIntelligenceAnalytics(
            total_entries=raw.total_entries,
            average_severity=raw.average_severity,
            maximum_severity=raw.maximum_severity,
            trend=raw.trend,
            category_frequency=raw.category_frequency,
            recurring_category_patterns=recurring_categories,
            recurring_description_pattern_count=sum(
                pattern.pattern_type == "description" for pattern in raw.recurring_patterns
            ),
            severity_by_mood_rating=raw.severity_by_mood_rating,
            severity_by_sleep_duration=raw.severity_by_sleep_duration,
        )
        lifestyle_input = LifestyleAnalysisInput(
            date_from=state["date_from"],
            date_to=state["date_to"],
            records=[
                LifestyleDailyRecord(
                    record_date=row.record_date,
                    mood_rating=row.mood_rating,
                    sleep_duration_hours=row.sleep_duration_hours,
                    sleep_quality=row.sleep_quality,
                )
                for row in mood_sleep_rows
            ],
            symptom_daily_trend=[
                DailySymptomSeverity(
                    date=date.fromisoformat(point.period_start),
                    average_severity=point.average_severity,
                    entry_count=point.entry_count,
                )
                for point in raw.trend
            ],
            symptom_severity_by_mood=[
                SeverityGroupComparison.model_validate(item.model_dump())
                for item in raw.severity_by_mood_rating
            ],
            symptom_severity_by_sleep_duration=[
                SeverityGroupComparison.model_validate(item.model_dump())
                for item in raw.severity_by_sleep_duration
            ],
        )
        warnings = [f"{omitted} recurring category patterns omitted from report context."] if omitted else []
        return {"analytics": analytics, "lifestyle_analysis_input": lifestyle_input, "warnings": warnings}
    except Exception:
        return {
            "execution_status": "failed",
            "error_code": "evidence_unavailable",
            "warnings": ["Patient evidence could not be loaded."],
        }


def symptom_analysis(state: HealthIntelligenceState) -> dict:
    if not _can_continue(state) or state.get("analytics") is None:
        return {}
    result = analyze_symptom_evidence(
        state["analytics"], date_from=state["date_from"], date_to=state["date_to"],
    )
    facts = [item.summary for item in result.key_findings if item.finding_type == "observed_fact"]
    observations = [item.summary for item in result.key_findings if item.finding_type == "interpretation"]
    observations.extend(f"Symptom analysis warning: {warning}" for warning in result.warnings)
    observations.extend(f"Symptom analysis limitation: {limitation}" for limitation in result.limitations)
    return {"symptom_evidence": HealthIntelligenceEvidence(
        recorded_facts=facts, analytical_observations=observations,
    ), "symptom_analysis_result": result}


def lifestyle_analysis(state: HealthIntelligenceState) -> dict:
    if not _can_continue(state) or state.get("lifestyle_analysis_input") is None:
        return {}
    result = analyze_lifestyle_evidence(state["lifestyle_analysis_input"])
    facts = [item.summary for item in result.key_findings if item.finding_type == "observed_fact"]
    observations = [item.summary for item in result.key_findings if item.finding_type == "comparison"]
    observations.extend(f"Lifestyle analysis warning: {warning}" for warning in result.warnings)
    observations.extend(f"Lifestyle analysis limitation: {limitation}" for limitation in result.limitations)
    return {"lifestyle_evidence": HealthIntelligenceEvidence(
        recorded_facts=facts, analytical_observations=observations,
    ), "lifestyle_analysis_result": result}


def medical_knowledge(state: HealthIntelligenceState) -> dict:
    """Run educational RAG with only the explicit question, never patient state."""
    if not _can_continue(state):
        return {}
    question = state.get("educational_question")
    if question is None:
        return {}
    result = analyze_medical_knowledge(MedicalKnowledgeInput(question=question))
    return {"medical_knowledge_result": result}


def health_report_agent(state: HealthIntelligenceState) -> dict:
    if not _can_continue(state):
        return {}
    analytics = state.get("analytics")
    symptom = state.get("symptom_analysis_result")
    lifestyle = state.get("lifestyle_analysis_result")
    if analytics is None or symptom is None or lifestyle is None:
        return {
            "execution_status": "failed",
            "error_code": "evidence_incomplete",
            "warnings": ["Required validated analysis results are unavailable."],
        }
    try:
        report = generate_health_report(HealthReportAgentInput(
            patient_id=state["patient_id"],
            date_from=state["date_from"],
            date_to=state["date_to"],
            analytics=analytics,
            symptom_analysis=symptom,
            lifestyle_analysis=lifestyle,
            educational_question=state.get("educational_question"),
            medical_knowledge=state.get("medical_knowledge_result"),
            orchestration_warnings=state.get("warnings", []),
        ))
    except Exception:
        return {
            "execution_status": "failed",
            "error_code": "invalid_report",
            "warnings": ["Validated report inputs could not be assembled."],
        }
    return {"report": report}


def validate_report(state: HealthIntelligenceState) -> dict:
    if not _can_continue(state):
        return {}
    report = state.get("report")
    if report is None:
        return {"execution_status": "failed", "error_code": "invalid_report", "warnings": ["A complete report was not produced."]}
    try:
        validated = HealthIntelligenceReport.model_validate(report.model_dump())
        symptom = state.get("symptom_analysis_result")
        lifestyle = state.get("lifestyle_analysis_result")
        if validated.symptom_analysis != symptom or validated.lifestyle_analysis != lifestyle:
            raise ValueError("Report does not preserve the validated specialist agent results")
        knowledge = state.get("medical_knowledge_result")
        if validated.medical_knowledge_context != knowledge:
            raise ValueError("Report medical context does not match the optional knowledge result")
        if knowledge is None and (validated.general_educational_information is not None or validated.educational_sources):
            raise ValueError("Report contains unrequested educational context")
    except Exception:
        return {"execution_status": "failed", "error_code": "invalid_report", "warnings": ["The generated report did not match the required structure."]}
    return {"report": validated, "execution_status": "succeeded"}
