"""Deterministic, read-only analysis of allowlisted mood/sleep evidence."""

from collections import Counter, defaultdict
from datetime import timedelta
from statistics import fmean

from backend.app.health_intelligence.lifestyle_schemas import (
    LifestyleAnalysisFinding,
    LifestyleAnalysisInput,
    LifestyleAnalysisResult,
)

MIN_CHECKINS_FOR_CHANGE_COMPARISON = 4


def analyze_lifestyle_evidence(data: LifestyleAnalysisInput) -> LifestyleAnalysisResult:
    """Summarize daily records and same-date severity comparisons without causal claims."""
    records = sorted(data.records, key=lambda item: item.record_date)
    window_days = (data.date_to - data.date_from).days + 1
    present_dates = {record.record_date for record in records}
    missing_dates = [
        data.date_from + timedelta(days=offset)
        for offset in range(window_days)
        if data.date_from + timedelta(days=offset) not in present_dates
    ]
    findings: list[LifestyleAnalysisFinding] = []
    warnings: list[str] = []
    limitations = [
        "Mood and sleep are stored together in one daily check-in; an absent date means both are missing.",
        "Same-date symptom comparisons are descriptive and do not establish causation.",
        "No mood or sleep notes, labels, diagnoses, or treatment conclusions are used.",
    ]

    if not records:
        warnings.append("No mood/sleep check-ins were recorded in the selected date range.")
        findings.append(LifestyleAnalysisFinding(
            code="no_lifestyle_records",
            finding_type="observed_fact",
            summary="No combined mood/sleep records were available in the selected date range.",
            supporting_metrics={"checkin_count": 0},
            evidence_references=["lifestyle.records[]", "request.date_from", "request.date_to"],
            sample_size=0,
        ))

    if missing_dates:
        findings.append(LifestyleAnalysisFinding(
            code="missing_checkins",
            finding_type="observed_fact",
            summary=(f"{len(missing_dates)} of {window_days} selected calendar dates had no combined "
                     "mood/sleep check-in; both fields are absent on those dates."),
            supporting_metrics={"missing_dates": len(missing_dates), "window_days": window_days},
            evidence_references=["lifestyle.records[].record_date", "request.date_from", "request.date_to"],
            sample_size=window_days,
        ))

    if records:
        mood_counts = Counter(record.mood_rating for record in records)
        mood_mean = fmean(record.mood_rating for record in records)
        mood_distribution = {str(rating): mood_counts.get(rating, 0) for rating in range(1, 6)}
        findings.append(LifestyleAnalysisFinding(
            code="mood_distribution",
            finding_type="observed_fact",
            summary=f"Mean recorded mood rating was {mood_mean:.2f}/5 across {len(records)} daily check-ins.",
            supporting_metrics={"average_mood_rating": round(mood_mean, 2), **{
                f"rating_{rating}_count": count for rating, count in mood_distribution.items()
            }},
            evidence_references=["lifestyle.records[].mood_rating"],
            sample_size=len(records),
        ))

        if len(records) >= MIN_CHECKINS_FOR_CHANGE_COMPARISON:
            midpoint = len(records) // 2
            earlier = fmean(item.mood_rating for item in records[:midpoint])
            later = fmean(item.mood_rating for item in records[midpoint:])
            difference = round(later - earlier, 2)
            findings.append(LifestyleAnalysisFinding(
                code="mood_change_comparison",
                finding_type="comparison",
                summary=(f"Mean recorded mood rating was {earlier:.2f}/5 in the earlier half and "
                         f"{later:.2f}/5 in the later half of check-in dates (difference {difference:+.2f})."),
                supporting_metrics={
                    "earlier_mean_rating": round(earlier, 2),
                    "later_mean_rating": round(later, 2),
                    "difference": difference,
                    "earlier_checkins": midpoint,
                    "later_checkins": len(records) - midpoint,
                },
                evidence_references=["lifestyle.records[].record_date", "lifestyle.records[].mood_rating"],
                sample_size=len(records),
            ))
        else:
            warnings.append(
                f"Mood change comparison requires at least {MIN_CHECKINS_FOR_CHANGE_COMPARISON} check-ins; "
                f"{len(records)} were available."
            )
            findings.append(LifestyleAnalysisFinding(
                code="mood_change_insufficient_data",
                finding_type="comparison",
                summary="Mood change was not compared because too few daily check-ins were available.",
                supporting_metrics={"checkins_available": len(records), "minimum_checkins": MIN_CHECKINS_FOR_CHANGE_COMPARISON},
                evidence_references=["lifestyle.records[].record_date", "lifestyle.records[].mood_rating"],
                sample_size=len(records),
            ))

        durations = [record.sleep_duration_hours for record in records]
        duration_counts = Counter(durations)
        findings.append(LifestyleAnalysisFinding(
            code="sleep_duration_summary",
            finding_type="observed_fact",
            summary=(f"Mean recorded sleep duration was {fmean(durations):.2f} hours per check-in "
                     f"across {len(records)} daily records; observed values ranged from "
                     f"{min(durations):g} to {max(durations):g} hours."),
            supporting_metrics={
                "average_hours": round(fmean(durations), 2),
                "minimum_hours": min(durations),
                "maximum_hours": max(durations),
            },
            evidence_references=["lifestyle.records[].sleep_duration_hours"],
            sample_size=len(records),
        ))
        findings.append(LifestyleAnalysisFinding(
            code="sleep_duration_distribution",
            finding_type="observed_fact",
            summary="Recorded sleep-duration values and their check-in counts are listed in supporting metrics.",
            supporting_metrics={f"{hours:g}_hours_count": count for hours, count in sorted(duration_counts.items())},
            evidence_references=["lifestyle.records[].sleep_duration_hours"],
            sample_size=len(records),
        ))

        quality_counts = Counter(record.sleep_quality for record in records)
        findings.append(LifestyleAnalysisFinding(
            code="sleep_quality_distribution",
            finding_type="observed_fact",
            summary=(f"Mean recorded sleep-quality rating was "
                     f"{fmean(record.sleep_quality for record in records):.2f}/5 across {len(records)} daily check-ins."),
            supporting_metrics={
                "average_quality": round(fmean(record.sleep_quality for record in records), 2),
                **{f"rating_{rating}_count": quality_counts.get(rating, 0) for rating in range(1, 6)},
            },
            evidence_references=["lifestyle.records[].sleep_quality"],
            sample_size=len(records),
        ))

    matched_count = 0
    for code, label, rows, source in (
        ("symptom_severity_by_mood", "mood rating", data.symptom_severity_by_mood, "analytics.severity_by_mood_rating[]"),
        ("symptom_severity_by_sleep_duration", "sleep-duration group", data.symptom_severity_by_sleep_duration, "analytics.severity_by_sleep_duration[]"),
    ):
        if rows:
            matched_count += sum(row.matching_symptom_entries for row in rows)
            metrics: dict[str, int | float | str] = {}
            for index, row in enumerate(rows, start=1):
                metrics[f"group_{index}"] = row.group
                metrics[f"group_{index}_average_severity"] = row.average_severity
                metrics[f"group_{index}_matching_symptom_entries"] = row.matching_symptom_entries
            findings.append(LifestyleAnalysisFinding(
                code=code,
                finding_type="comparison",
                summary=(f"Existing analytics provide same-date symptom-severity comparisons by {label}; "
                         "group means and matching-entry counts are in supporting metrics."),
                supporting_metrics=metrics,
                evidence_references=[source],
                sample_size=sum(row.matching_symptom_entries for row in rows),
            ))

    quality_by_date = {record.record_date: record.sleep_quality for record in records}
    trend_by_date = {point.date: point for point in data.symptom_daily_trend}
    severity_by_quality: dict[int, list[float]] = defaultdict(list)
    for day, quality in quality_by_date.items():
        if day in trend_by_date:
            severity_by_quality[quality].append(trend_by_date[day].average_severity)
    if severity_by_quality:
        matched_count += sum(len(values) for values in severity_by_quality.values())
        metrics = {}
        for quality, values in sorted(severity_by_quality.items()):
            metrics[f"quality_{quality}_average_symptom_severity"] = round(fmean(values), 2)
            metrics[f"quality_{quality}_matched_dates"] = len(values)
        findings.append(LifestyleAnalysisFinding(
            code="symptom_severity_by_sleep_quality",
            finding_type="comparison",
            summary=("Daily symptom-severity averages are compared with same-date sleep-quality ratings; "
                     "each quality group reports matched dates, without causal interpretation."),
            supporting_metrics=metrics,
            evidence_references=[
                "analytics.trend[].period_start",
                "analytics.trend[].average_severity",
                "lifestyle.records[].record_date",
                "lifestyle.records[].sleep_quality",
            ],
            sample_size=sum(len(values) for values in severity_by_quality.values()),
        ))

    if not matched_count:
        findings.append(LifestyleAnalysisFinding(
            code="no_matched_symptom_data",
            finding_type="observed_fact",
            summary="No same-date symptom-severity evidence was available for comparison with mood or sleep.",
            supporting_metrics={"matched_symptom_entries_or_dates": 0},
            evidence_references=[
                "analytics.severity_by_mood_rating[]",
                "analytics.severity_by_sleep_duration[]",
                "analytics.trend[].period_start",
                "lifestyle.records[].record_date",
            ],
            sample_size=0,
        ))

    explanation = (
        "No mood or sleep records were available in this date range."
        if not records
        else f"Lifestyle summaries use {len(records)} recorded daily check-ins; matching symptom comparisons use only shared UTC dates."
    )
    status = "empty" if not records else "insufficient_data" if len(records) < MIN_CHECKINS_FOR_CHANGE_COMPARISON else "complete"
    return LifestyleAnalysisResult(
        agent_status=status,
        key_findings=findings,
        missing_mood_dates=missing_dates,
        missing_sleep_dates=missing_dates.copy(),
        warnings=warnings,
        limitations=limitations,
        concise_explanation=explanation,
    )
