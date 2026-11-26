"""Deterministic, bounded analysis of precomputed symptom analytics."""

from datetime import date
from statistics import fmean

from backend.app.schemas import HealthIntelligenceAnalytics
from backend.app.health_intelligence.symptom_schemas import SymptomAnalysisFinding, SymptomAnalysisResult

MIN_DATES_FOR_TREND_COMPARISON = 4
MEANINGFUL_SEVERITY_CHANGE = 1.0


def analyze_symptom_evidence(
    analytics: HealthIntelligenceAnalytics,
    *,
    date_from: date,
    date_to: date,
) -> SymptomAnalysisResult:
    """Interpret only bounded aggregates; all base counts and severities come from analytics."""
    period = f"{date_from.isoformat()} through {date_to.isoformat()} UTC (inclusive)"
    findings: list[SymptomAnalysisFinding] = []
    warnings: list[str] = []
    limitations = [
        "Descriptive symptom tracking cannot establish a diagnosis or cause.",
        "Trend comparisons use only dates with entries; unrecorded dates are not treated as zero severity.",
        "The 1.0-point change threshold is a reporting heuristic, not a clinically validated threshold.",
    ]

    if analytics.total_entries == 0:
        findings.append(SymptomAnalysisFinding(
            code="no_symptoms",
            finding_type="observed_fact",
            summary=f"No symptom entries were recorded from {period}.",
            supporting_metrics={"total_entries": 0},
            evidence_references=["analytics.total_entries"],
        ))
        limitations.append("Frequency, severity, category, recurrence, and trend findings are unavailable without symptom entries.")
        return SymptomAnalysisResult(
            agent_status="empty",
            key_findings=findings,
            warnings=[],
            limitations=limitations,
            concise_explanation="There are no symptom entries in the selected date range to analyze.",
        )

    findings.append(SymptomAnalysisFinding(
        code="symptom_frequency",
        finding_type="observed_fact",
        summary=f"{analytics.total_entries} symptom entries were recorded during the selected period.",
        supporting_metrics={"total_entries": analytics.total_entries, "date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
        evidence_references=["analytics.total_entries", "request.date_from", "request.date_to"],
    ))

    if analytics.average_severity is not None and analytics.maximum_severity is not None:
        findings.append(SymptomAnalysisFinding(
            code="severity_summary",
            finding_type="observed_fact",
            summary=(f"The existing analytics returned an average severity of {analytics.average_severity:.2f}/10 "
                     f"and a highest severity of {analytics.maximum_severity}/10."),
            supporting_metrics={
                "average_severity": analytics.average_severity,
                "maximum_severity": analytics.maximum_severity,
            },
            evidence_references=["analytics.average_severity", "analytics.maximum_severity"],
        ))
    else:
        warnings.append("Average and maximum severity were unavailable in the supplied analytics.")

    if analytics.category_frequency:
        distribution = "; ".join(
            f"{row.category}: {row.entry_count}" for row in analytics.category_frequency
        )
        findings.append(SymptomAnalysisFinding(
            code="category_distribution",
            finding_type="observed_fact",
            summary=f"Recorded entry counts by category were {distribution}.",
            supporting_metrics={row.category: row.entry_count for row in analytics.category_frequency},
            evidence_references=["analytics.category_frequency[].category", "analytics.category_frequency[].entry_count"],
        ))
        if any(row.category == "Uncategorized" for row in analytics.category_frequency):
            warnings.append("Some symptom entries have no category and are included as Uncategorized.")
    else:
        warnings.append("Category distribution was unavailable in the supplied analytics.")

    recurring_categories = analytics.recurring_category_patterns
    if recurring_categories:
        findings.append(SymptomAnalysisFinding(
            code="recurring_categories",
            finding_type="observed_fact",
            summary="Categories meeting the existing three-distinct-date recurrence rule: "
                    + ", ".join(item.label for item in recurring_categories) + ".",
            supporting_metrics={item.label: item.occurrence_count for item in recurring_categories},
            evidence_references=["analytics.recurring_category_patterns[]"],
        ))
    if analytics.recurring_description_pattern_count:
        findings.append(SymptomAnalysisFinding(
            code="recurring_descriptions",
            finding_type="observed_fact",
            summary=(f"{analytics.recurring_description_pattern_count} normalized symptom-description patterns "
                     "met the three-distinct-date recurrence rule; free-text descriptions are withheld."),
            supporting_metrics={"pattern_count": analytics.recurring_description_pattern_count},
            evidence_references=["analytics.recurring_description_pattern_count"],
        ))

    trend = analytics.trend
    if len(trend) < MIN_DATES_FOR_TREND_COMPARISON:
        warnings.append(
            f"Severity change was not assessed: {len(trend)} dates with entries were found; "
            f"at least {MIN_DATES_FOR_TREND_COMPARISON} are required."
        )
        findings.append(SymptomAnalysisFinding(
            code="trend_insufficient_data",
            finding_type="interpretation",
            summary="There are not enough dates with symptom entries to compare earlier and later severity trends.",
            supporting_metrics={"observed_dates": len(trend), "minimum_dates": MIN_DATES_FOR_TREND_COMPARISON},
            evidence_references=["analytics.trend[].period_start"],
        ))
    else:
        midpoint = len(trend) // 2
        earlier = fmean(point.average_severity for point in trend[:midpoint])
        later = fmean(point.average_severity for point in trend[midpoint:])
        change = round(later - earlier, 2)
        if change >= MEANINGFUL_SEVERITY_CHANGE:
            code = "severity_increase"
            direction = "increased"
        elif change <= -MEANINGFUL_SEVERITY_CHANGE:
            code = "severity_decrease"
            direction = "decreased"
        else:
            code = "severity_stable"
            direction = "did not change by the defined meaningful threshold"
        findings.append(SymptomAnalysisFinding(
            code=code,
            finding_type="interpretation",
            summary=(f"Mean daily severity {direction} between the earlier and later halves of observed dates "
                     f"(change {change:+.2f}/10; meaningful threshold ±{MEANINGFUL_SEVERITY_CHANGE:.1f})."),
            supporting_metrics={
                "earlier_mean_daily_severity": round(earlier, 2),
                "later_mean_daily_severity": round(later, 2),
                "change": change,
                "meaningful_threshold": MEANINGFUL_SEVERITY_CHANGE,
            },
            evidence_references=["analytics.trend[].period_start", "analytics.trend[].average_severity"],
        ))

    interpretation_summaries = [item.summary for item in findings if item.finding_type == "interpretation"]
    if interpretation_summaries:
        explanation = " ".join(interpretation_summaries)
    else:
        explanation = "Symptom counts and severity summaries are available; trend interpretation is limited by the observed dates."
    status = "insufficient_data" if len(trend) < MIN_DATES_FOR_TREND_COMPARISON else "complete"
    return SymptomAnalysisResult(
        agent_status=status,
        key_findings=findings,
        warnings=warnings,
        limitations=limitations,
        concise_explanation=explanation,
    )
