from datetime import date
import json
import logging

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from backend.app.health_intelligence.lifestyle_agent import analyze_lifestyle_evidence
from backend.app.health_intelligence.lifestyle_schemas import (
    DailySymptomSeverity,
    LifestyleAnalysisInput,
    LifestyleDailyRecord,
)
from backend.app.health_intelligence.report_agent import (
    AUTHORIZATION_LIMITATION,
    _AIHealthReportText,
    HealthReportAgentInput,
    generate_health_report,
)
from backend.app.health_intelligence.symptom_agent import analyze_symptom_evidence
from backend.app.schemas import (
    AnalyticsBucket,
    HealthIntelligenceAnalytics,
    HealthIntelligenceSource,
    MedicalKnowledgeResult,
)
from backend.app.services.ai_service import MissingAPIKeyError


def _components(with_records=True):
    start, end = date(2025, 1, 1), date(2025, 1, 7)
    analytics = HealthIntelligenceAnalytics(
        total_entries=1 if with_records else 0,
        average_severity=5.0 if with_records else None,
        maximum_severity=5 if with_records else None,
        trend=[AnalyticsBucket(
            period_start="2025-01-03", average_severity=5.0, maximum_severity=5, entry_count=1,
        )] if with_records else [],
        category_frequency=[],
        recurring_category_patterns=[],
        recurring_description_pattern_count=0,
        severity_by_mood_rating=[],
        severity_by_sleep_duration=[],
    )
    symptom = analyze_symptom_evidence(analytics, date_from=start, date_to=end)
    lifestyle_input = LifestyleAnalysisInput(
        date_from=start,
        date_to=end,
        records=[LifestyleDailyRecord(
            record_date=date(2025, 1, 3), mood_rating=3, sleep_duration_hours=7.0, sleep_quality=4,
        )] if with_records else [],
        symptom_daily_trend=[DailySymptomSeverity(
            date=date(2025, 1, 3), average_severity=5.0, entry_count=1,
        )] if with_records else [],
        symptom_severity_by_mood=[],
        symptom_severity_by_sleep_duration=[],
    )
    lifestyle = analyze_lifestyle_evidence(lifestyle_input)
    return start, end, analytics, symptom, lifestyle


def _input(with_records=True, **overrides):
    start, end, analytics, symptom, lifestyle = _components(with_records)
    values = {
        "patient_id": "synthetic-patient-42",
        "date_from": start,
        "date_to": end,
        "analytics": analytics,
        "symptom_analysis": symptom,
        "lifestyle_analysis": lifestyle,
        "educational_question": None,
        "medical_knowledge": None,
        "orchestration_warnings": [],
    }
    values.update(overrides)
    return HealthReportAgentInput(**values)


def _mock_gemini(monkeypatch, output):
    prompts = []

    def create_llm(api_key, model):
        def invoke(prompt):
            prompts.append(prompt.to_string())
            return AIMessage(content=output)

        return RunnableLambda(invoke)

    monkeypatch.setattr("backend.app.health_intelligence.report_agent.get_gemini_config", lambda: ("secret-key", "test-model"))
    monkeypatch.setattr("backend.app.health_intelligence.report_agent.create_llm", create_llm)
    return prompts


def test_report_agent_builds_all_sections_and_uses_structured_gemini(monkeypatch):
    prompts = _mock_gemini(monkeypatch, '{"explanations":["Recorded severity varied across the selected dates."]}')
    report = generate_health_report(_input())

    assert report.executive_summary
    assert report.patient_recorded_facts
    assert report.deterministic_observations
    assert report.symptom_analysis is not None
    assert report.lifestyle_analysis is not None
    assert report.ai_explanation_status == "generated"
    assert report.ai_generated_explanations == ["Recorded severity varied across the selected dates."]
    assert "synthetic-patient-42" not in prompts[0]
    assert "secret-key" not in prompts[0]
    assert "MedlinePlus" not in prompts[0]
    assert "https://" not in prompts[0]


def test_report_prompt_requires_grounded_neutral_output_and_json_only(monkeypatch):
    prompts = _mock_gemini(
        monkeypatch,
        '{"explanations":["There are too few dates to compare symptom trends over time."]}',
    )
    report = generate_health_report(_input())

    prompt = prompts[0]
    assert "plain, neutral, non-clinical language" in prompt
    assert "directly supported by the supplied deterministic observations" in prompt
    assert "Do not add, infer, or generalize any finding" in prompt
    assert "Do not include digits, numbers, dates" in prompt
    assert "Return only the structured JSON object" in prompt
    assert report.ai_explanation_status == "generated"
    assert report.ai_generated_explanations == [
        "There are too few dates to compare symptom trends over time."
    ]


def test_empty_histories_skip_gemini_and_report_missing_evidence(monkeypatch):
    def must_not_call():
        raise AssertionError("Gemini must not be called for empty histories")

    monkeypatch.setattr("backend.app.health_intelligence.report_agent.get_gemini_config", must_not_call)
    report = generate_health_report(_input(with_records=False))
    assert report.ai_explanation_status == "skipped_no_records"
    assert report.ai_generated_explanations == []
    assert "No symptom entries" in report.executive_summary
    assert report.warnings and AUTHORIZATION_LIMITATION in report.warnings


@pytest.mark.parametrize("failure", [
    MissingAPIKeyError("missing"),
    RuntimeError("provider failed"),
])
def test_gemini_failures_preserve_deterministic_findings(monkeypatch, failure):
    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr("backend.app.health_intelligence.report_agent.get_gemini_config", lambda: ("secret", "model"))
    monkeypatch.setattr("backend.app.health_intelligence.report_agent.create_llm", fail)
    report = generate_health_report(_input())
    assert report.ai_explanation_status == "unavailable"
    assert report.ai_generated_explanations == []
    assert report.patient_recorded_facts
    assert report.deterministic_observations
    assert any("deterministic report findings are preserved" in item for item in report.warnings)


@pytest.mark.parametrize("stage", [
    "gemini_configuration_lookup",
    "model_client_initialization",
    "request_preparation",
    "provider_invocation",
    "response_parsing",
    "structured_output_validation",
])
def test_generation_failures_log_stage_without_sensitive_details(monkeypatch, caplog, stage):
    from backend.app.health_intelligence import report_agent

    secret = "AIzaFAKE_SECRET patient=private-patient symptom=private-description prompt=private-prompt 7"

    def fail(*args, **kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(report_agent, "get_gemini_config", lambda: ("FAKE_API_KEY_VALUE", "test-model"))
    monkeypatch.setattr(report_agent, "create_llm", lambda **kwargs: fail())

    if stage == "gemini_configuration_lookup":
        monkeypatch.setattr(report_agent, "get_gemini_config", fail)
    elif stage == "model_client_initialization":
        pass
    elif stage == "request_preparation":
        class FailingPrompt:
            def invoke(self, values):
                raise RuntimeError(secret)

        class UnusedClient:
            def invoke(self, prompt):
                raise AssertionError("request preparation should fail before provider invocation")

        monkeypatch.setattr(report_agent, "_REPORT_PROMPT", FailingPrompt())
        monkeypatch.setattr(report_agent, "create_llm", lambda **kwargs: UnusedClient())
    elif stage == "provider_invocation":
        class FailingClient:
            def invoke(self, prompt):
                raise RuntimeError(secret)

        monkeypatch.setattr(report_agent, "create_llm", lambda **kwargs: FailingClient())
    elif stage == "response_parsing":
        class InvalidJsonClient:
            def invoke(self, prompt):
                return AIMessage(content=f"not-json {secret}")

        monkeypatch.setattr(report_agent, "create_llm", lambda **kwargs: InvalidJsonClient())
    else:
        class InvalidSchemaClient:
            def invoke(self, prompt):
                return AIMessage(content=json.dumps({"explanations": [secret]}))

        monkeypatch.setattr(report_agent, "create_llm", lambda **kwargs: InvalidSchemaClient())

    with caplog.at_level(logging.WARNING, logger="backend.app.health_intelligence.report_agent"):
        report = generate_health_report(_input())

    assert f"stage={stage}" in caplog.text
    assert "exception_class=" in caplog.text
    assert "message=" in caplog.text
    assert secret not in caplog.text
    assert "FAKE_API_KEY_VALUE" not in caplog.text
    assert "synthetic-patient-42" not in caplog.text
    assert report.ai_explanation_status == "unavailable"
    assert report.ai_generated_explanations == []
    assert report.patient_recorded_facts and report.deterministic_observations
    assert secret not in str(report.model_dump())


def test_invalid_gemini_output_is_rejected_without_losing_deterministic_report(monkeypatch):
    prompts = _mock_gemini(monkeypatch, '{"explanations":["A condition is caused by X."]}')
    report = generate_health_report(_input())
    assert prompts
    assert report.ai_explanation_status == "unavailable"
    assert report.ai_generated_explanations == []
    assert report.patient_recorded_facts


@pytest.mark.parametrize(("explanation", "expected_code"), [
    ("The average severity is 4.", "numeric_value"),
    ("This condition causes the symptom.", "clinical_claim_filter"),
])
def test_explanation_validation_uses_distinct_safe_codes(explanation, expected_code):
    with pytest.raises(ValidationError) as exc_info:
        _AIHealthReportText.model_validate({"explanations": [explanation]})

    errors = exc_info.value.errors(include_input=False)
    assert errors[0]["type"] == expected_code
    assert errors[0]["loc"] == ("explanations",)


def test_explanation_validation_accepts_safe_supported_text():
    result = _AIHealthReportText.model_validate({
        "explanations": ["The entries show a pattern across the selected dates."],
    })
    assert result.explanations == ["The entries show a pattern across the selected dates."]


@pytest.mark.parametrize("explanation", [
    "The patient has asthma.",
    "Take medication as prescribed.",
    "You should take medication.",
    "Treatment is recommended.",
    "Stress causes headaches.",
    "The diagnosis is asthma.",
])
def test_explanation_validator_rejects_clinical_claims(explanation):
    with pytest.raises(ValidationError) as exc_info:
        _AIHealthReportText.model_validate({"explanations": [explanation]})

    assert exc_info.value.errors(include_input=False)[0]["type"] == "clinical_claim_filter"


@pytest.mark.parametrize("explanation", [
    "The notes include no diagnosis or disease details.",
    "Medication details are absent from the notes.",
    "No treatment information was recorded.",
    "No causal link is established by these records.",
])
def test_explanation_validator_allows_neutral_clinical_term_mentions(explanation):
    result = _AIHealthReportText.model_validate({"explanations": [explanation]})
    assert result.explanations == [explanation]


@pytest.mark.parametrize(("output", "expected_code"), [
    ('{"explanations":["The average severity is 4."]}', "numeric_value"),
    ('{"explanations":["This condition causes the symptom."]}', "clinical_claim_filter"),
])
def test_validation_failure_logs_safe_code_and_preserves_fallback(
    monkeypatch,
    caplog,
    output,
    expected_code,
):
    _mock_gemini(monkeypatch, output)

    with caplog.at_level(logging.WARNING, logger="backend.app.health_intelligence.report_agent"):
        report = generate_health_report(_input())

    assert "stage=structured_output_validation" in caplog.text
    assert f"diagnostic_code={expected_code}" in caplog.text
    assert "response content redacted" in caplog.text
    assert "The average severity" not in caplog.text
    assert "This condition causes" not in caplog.text
    assert report.ai_explanation_status == "unavailable"
    assert report.ai_generated_explanations == []
    assert report.patient_recorded_facts and report.deterministic_observations


def test_health_report_includes_education_only_for_matching_explicit_question(monkeypatch):
    monkeypatch.setattr(
        "backend.app.health_intelligence.report_agent.get_gemini_config",
        lambda: (_ for _ in ()).throw(MissingAPIKeyError("mock missing key")),
    )
    knowledge = MedicalKnowledgeResult(
        agent_status="complete",
        question="What is a fever?",
        answer="General educational answer.",
        sources=[HealthIntelligenceSource(title="MedlinePlus - Fever", url="https://medlineplus.gov/fever.html")],
    )
    report = generate_health_report(_input(
        educational_question="What is a fever?", medical_knowledge=knowledge,
    ))
    assert report.general_educational_information == "General educational answer."
    assert report.educational_sources[0].title == "MedlinePlus - Fever"
    assert report.medical_knowledge_context == knowledge
    assert report.ai_generated_explanations == []


def test_report_input_rejects_out_of_scope_evidence_and_unrequested_knowledge():
    start, end, analytics, symptom, lifestyle = _components()
    invalid_analytics = analytics.model_copy(update={
        "trend": [AnalyticsBucket(
            period_start="2025-02-01", average_severity=5, maximum_severity=5, entry_count=1,
        )],
    })
    with pytest.raises(ValidationError):
        HealthReportAgentInput(
            patient_id="p", date_from=start, date_to=end, analytics=invalid_analytics,
            symptom_analysis=symptom, lifestyle_analysis=lifestyle,
        )
    knowledge = MedicalKnowledgeResult(
        agent_status="no_relevant_information", question="What is a fever?", answer="Not found.",
    )
    with pytest.raises(ValidationError):
        _input(medical_knowledge=knowledge)


def test_final_report_schema_rejects_invalid_shape():
    report = generate_health_report(_input(with_records=False))
    invalid = report.model_dump()
    invalid.pop("disclaimer")
    with pytest.raises(ValidationError):
        type(report).model_validate(invalid)
