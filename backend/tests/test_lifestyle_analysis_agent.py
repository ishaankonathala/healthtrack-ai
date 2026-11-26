from datetime import date

import pytest
from pydantic import ValidationError

from backend.app.health_intelligence.lifestyle_agent import analyze_lifestyle_evidence
from backend.app.health_intelligence.lifestyle_schemas import (
    DailySymptomSeverity,
    LifestyleAnalysisInput,
    LifestyleDailyRecord,
)


def _input(records=(), trend=(), start=date(2025, 1, 1), end=date(2025, 1, 7)):
    return LifestyleAnalysisInput(
        date_from=start,
        date_to=end,
        records=list(records),
        symptom_daily_trend=list(trend),
        symptom_severity_by_mood=[],
        symptom_severity_by_sleep_duration=[],
    )


def _record(day, mood=3, hours=7.0, quality=3):
    return LifestyleDailyRecord(
        record_date=date.fromisoformat(day),
        mood_rating=mood,
        sleep_duration_hours=hours,
        sleep_quality=quality,
    )


def _finding(result, code):
    return next(item for item in result.key_findings if item.code == code)


def test_normal_history_has_distributions_trend_and_sample_sizes():
    records = [
        _record("2025-01-01", 2, 6.5, 2),
        _record("2025-01-02", 3, 7, 3),
        _record("2025-01-04", 4, 8, 4),
        _record("2025-01-07", 5, 7, 5),
    ]
    result = analyze_lifestyle_evidence(_input(records))

    assert result.agent_status == "complete"
    mood = _finding(result, "mood_distribution")
    assert mood.supporting_metrics["average_mood_rating"] == 3.5
    assert mood.supporting_metrics["rating_5_count"] == 1
    assert mood.sample_size == 4
    change = _finding(result, "mood_change_comparison")
    assert change.supporting_metrics["earlier_mean_rating"] == 2.5
    assert change.supporting_metrics["later_mean_rating"] == 4.5
    duration = _finding(result, "sleep_duration_summary")
    assert duration.supporting_metrics["average_hours"] == 7.12
    assert duration.sample_size == 4
    quality = _finding(result, "sleep_quality_distribution")
    assert quality.supporting_metrics["average_quality"] == 3.5
    assert result.missing_mood_dates == [date(2025, 1, 3), date(2025, 1, 5), date(2025, 1, 6)]
    assert result.missing_sleep_dates == result.missing_mood_dates


def test_empty_history_does_not_interpret_missing_as_zero():
    result = analyze_lifestyle_evidence(_input())
    assert result.agent_status == "empty"
    assert not any("0.00" in item.summary for item in result.key_findings)
    assert len(result.missing_mood_dates) == 7
    assert _finding(result, "no_lifestyle_records").sample_size == 0


def test_incomplete_history_uses_only_recorded_values_and_warns():
    result = analyze_lifestyle_evidence(_input([_record("2025-01-05", mood=4, hours=5.25, quality=2)]))
    assert result.agent_status == "insufficient_data"
    assert _finding(result, "mood_change_insufficient_data").sample_size == 1
    assert _finding(result, "sleep_duration_summary").supporting_metrics["average_hours"] == 5.25
    assert "1 were available" in result.warnings[0]


def test_same_date_symptom_comparison_is_descriptive_and_scoped_to_matching_dates():
    records = [_record("2025-01-02", quality=2), _record("2025-01-04", quality=4)]
    trend = [
        DailySymptomSeverity(date=date(2025, 1, 2), average_severity=8, entry_count=2),
        DailySymptomSeverity(date=date(2025, 1, 3), average_severity=10, entry_count=1),
    ]
    result = analyze_lifestyle_evidence(_input(records, trend))
    comparison = _finding(result, "symptom_severity_by_sleep_quality")
    assert comparison.sample_size == 1
    assert comparison.supporting_metrics["quality_2_average_symptom_severity"] == 8
    assert "quality_4_average_symptom_severity" not in comparison.supporting_metrics
    assert "caus" in " ".join(result.limitations).lower()
    assert not any("causes" in finding.summary.lower() for finding in result.key_findings)


def test_analytics_comparisons_are_reused_without_recalculation():
    value = _input([_record("2025-01-02")]).model_dump()
    value["symptom_severity_by_mood"] = [{
        "group": "3", "average_severity": 6.5, "matching_symptom_entries": 2,
    }]
    value["symptom_severity_by_sleep_duration"] = [{
        "group": "6-<7", "average_severity": 5.0, "matching_symptom_entries": 1,
    }]
    result = analyze_lifestyle_evidence(LifestyleAnalysisInput.model_validate(value))
    by_mood = _finding(result, "symptom_severity_by_mood")
    by_sleep = _finding(result, "symptom_severity_by_sleep_duration")
    assert by_mood.supporting_metrics["group_1_average_severity"] == 6.5
    assert by_mood.sample_size == 2
    assert by_sleep.sample_size == 1


def test_input_rejects_out_of_range_or_duplicate_dates_and_free_text():
    with pytest.raises(ValidationError):
        _input([_record("2024-12-31")])
    with pytest.raises(ValidationError):
        _input([_record("2025-01-02"), _record("2025-01-02")])
    with pytest.raises(ValidationError):
        LifestyleDailyRecord.model_validate({
            **_record("2025-01-02").model_dump(), "sleep_notes": "private text",
        })
    with pytest.raises(ValidationError):
        LifestyleDailyRecord(record_date=date(2025, 1, 2), mood_rating=6, sleep_duration_hours=7, sleep_quality=3)


def test_finding_schema_rejects_invalid_structured_output():
    result = analyze_lifestyle_evidence(_input([_record("2025-01-02")]))
    bad = result.model_dump()
    bad["key_findings"][0]["unexpected"] = "value"
    with pytest.raises(ValidationError):
        type(result).model_validate(bad)


def test_no_gemini_dependency_or_free_text_is_used_by_deterministic_component():
    result = analyze_lifestyle_evidence(_input([_record("2025-01-02")]))
    serialized = result.model_dump_json()
    assert "sleep_notes" not in serialized
    assert "Gemini" not in serialized
    assert result.agent_status == "insufficient_data"
