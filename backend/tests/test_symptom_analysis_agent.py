from datetime import date

import pytest
from pydantic import ValidationError

from backend.app.health_intelligence import symptom_agent
from backend.app.health_intelligence.nodes import symptom_analysis
from backend.app.health_intelligence.state import HealthIntelligenceState
from backend.app.health_intelligence.symptom_schemas import SymptomAnalysisResult
from backend.app.schemas import (
    AnalyticsBucket,
    CategoryAnalytics,
    HealthIntelligenceAnalytics,
    RecurringSymptomPattern,
)


def _analytics(*, total=6, trend=(2.0, 3.0, 5.0, 6.0), categories=None, recurring=None, description_patterns=0):
    points = [
        AnalyticsBucket(
            period_start=f"2025-01-{index + 1:02d}",
            average_severity=value,
            maximum_severity=int(value),
            entry_count=1,
        )
        for index, value in enumerate(trend)
    ]
    return HealthIntelligenceAnalytics(
        total_entries=total,
        average_severity=4.5 if total else None,
        maximum_severity=8 if total else None,
        trend=points,
        category_frequency=categories if categories is not None else [
            CategoryAnalytics(category="Fever", entry_count=4, average_severity=5.0),
            CategoryAnalytics(category="Uncategorized", entry_count=2, average_severity=3.5),
        ],
        recurring_category_patterns=recurring if recurring is not None else [
            RecurringSymptomPattern(
                pattern_type="category", label="Fever", occurrence_count=4,
                distinct_dates=["2025-01-01", "2025-01-02", "2025-01-03"],
            ),
        ],
        recurring_description_pattern_count=description_patterns,
        severity_by_mood_rating=[],
        severity_by_sleep_duration=[],
    )


def _run(analytics):
    return symptom_agent.analyze_symptom_evidence(
        analytics, date_from=date(2025, 1, 1), date_to=date(2025, 1, 31),
    )


def test_normal_history_returns_valid_findings_and_traceable_metrics():
    result = _run(_analytics(description_patterns=2))
    assert result.agent_status == "complete"
    findings = {finding.code: finding for finding in result.key_findings}
    assert findings["symptom_frequency"].supporting_metrics["total_entries"] == 6
    assert "analytics.total_entries" in findings["symptom_frequency"].evidence_references
    assert findings["severity_summary"].supporting_metrics["maximum_severity"] == 8
    assert findings["category_distribution"].supporting_metrics["Uncategorized"] == 2
    assert findings["recurring_categories"].supporting_metrics["Fever"] == 4
    assert findings["recurring_descriptions"].supporting_metrics["pattern_count"] == 2
    assert findings["severity_increase"].supporting_metrics["change"] == 3.0
    assert "diagnosis" not in result.concise_explanation.lower()


def test_empty_history_reports_empty_without_inventing_metrics():
    analytics = _analytics(total=0, trend=(), categories=[], recurring=[])
    result = _run(analytics)
    assert result.agent_status == "empty"
    assert result.key_findings[0].code == "no_symptoms"
    assert result.key_findings[0].supporting_metrics == {"total_entries": 0}
    assert not any(finding.code == "severity_summary" for finding in result.key_findings)
    assert result.warnings == []


def test_missing_categories_are_reported_as_uncategorized_with_warning():
    result = _run(_analytics(categories=[
        CategoryAnalytics(category="Uncategorized", entry_count=3, average_severity=4.0),
    ]))
    finding = next(item for item in result.key_findings if item.code == "category_distribution")
    assert finding.supporting_metrics == {"Uncategorized": 3}
    assert any("no category" in warning for warning in result.warnings)


def test_recurring_results_reference_analytics_without_exposing_descriptions():
    result = _run(_analytics(description_patterns=3))
    finding = next(item for item in result.key_findings if item.code == "recurring_descriptions")
    assert finding.supporting_metrics == {"pattern_count": 3}
    assert finding.evidence_references == ["analytics.recurring_description_pattern_count"]
    assert "private symptom phrase" not in finding.summary


@pytest.mark.parametrize(
    ("trend", "expected_code", "expected_change"),
    [((7.0, 6.0, 3.0, 2.0), "severity_decrease", -4.0), ((3.0, 4.0, 4.0, 4.0), "severity_stable", 0.5)],
)
def test_decreasing_or_nonmeaningful_trend_is_deterministic(trend, expected_code, expected_change):
    result = _run(_analytics(trend=trend))
    finding = next(item for item in result.key_findings if item.code in {
        "severity_increase", "severity_decrease", "severity_stable",
    })
    assert finding.code == expected_code
    assert finding.supporting_metrics["change"] == expected_change


def test_insufficient_trend_dates_are_reported_without_a_direction():
    result = _run(_analytics(trend=(4.0, 8.0)))
    assert result.agent_status == "insufficient_data"
    finding = next(item for item in result.key_findings if item.code == "trend_insufficient_data")
    assert finding.supporting_metrics == {"observed_dates": 2, "minimum_dates": 4}
    assert not any(item.code in {"severity_increase", "severity_decrease", "severity_stable"} for item in result.key_findings)


def test_invalid_agent_result_is_rejected_by_schema():
    with pytest.raises(ValidationError):
        SymptomAnalysisResult.model_validate({
            "agent_status": "guessing", "key_findings": [], "warnings": [],
            "limitations": [], "concise_explanation": "",
        })


def test_deterministic_node_does_not_call_gemini(monkeypatch):
    from backend.app.health_intelligence import nodes

    def fail_if_called(*args, **kwargs):
        raise AssertionError("symptom analysis is deterministic and must not call Gemini")

    monkeypatch.setattr(nodes, "create_llm", fail_if_called)
    state: HealthIntelligenceState = {
        "execution_status": "running",
        "date_from": date(2025, 1, 1),
        "date_to": date(2025, 1, 31),
        "analytics": _analytics(),
    }
    result = nodes.symptom_analysis(state)
    assert result["symptom_analysis_result"].agent_status == "complete"
    assert result["symptom_evidence"].recorded_facts
