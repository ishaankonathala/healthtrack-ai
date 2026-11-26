from collections import defaultdict
import re
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import DailyMoodSleepRecord, SymptomLog
from backend.app.schemas import (
    AdvancedAnalyticsResponse, AnalyticsBucket, AnalyticsResponse, CategoryAnalytics,
    DailySeverityPoint, RecurringSymptomPattern, SeverityComparison,
)

ANALYTICS_WINDOW_DAYS = 30
RECURRING_DISTINCT_DATE_THRESHOLD = 3


def _normalize_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware in UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_patient_analytics(
    db: Session,
    patient_id: str,
    now: datetime | None = None,
) -> AnalyticsResponse:
    """Compute 30-day symptom analytics for a patient from SymptomLog records."""
    current_time = _normalize_utc(now) if now is not None else datetime.now(timezone.utc)
    window_start = current_time - timedelta(days=ANALYTICS_WINDOW_DAYS)

    stmt = (
        select(SymptomLog)
        .where(
            SymptomLog.patient_id == patient_id,
            SymptomLog.timestamp >= window_start,
            SymptomLog.timestamp <= current_time,
        )
        .order_by(SymptomLog.timestamp.asc())
    )
    records = list(db.scalars(stmt).all())

    # Double-check window boundaries in UTC in case stored timestamps had offsets
    in_window: list[tuple[datetime, int]] = []
    for record in records:
        ts_utc = _normalize_utc(record.timestamp)
        if window_start <= ts_utc <= current_time:
            in_window.append((ts_utc, record.severity))

    if not in_window:
        return AnalyticsResponse(
            patient_id=patient_id,
            window_days=ANALYTICS_WINDOW_DAYS,
            total_entries=0,
            average_severity=None,
            highest_severity=None,
            daily_trend=[],
        )

    severities = [sev for _, sev in in_window]
    total_entries = len(severities)
    average_severity = round(sum(severities) / total_entries, 2)
    highest_severity = max(severities)

    daily_buckets: dict[str, list[int]] = defaultdict(list)
    for ts_utc, sev in in_window:
        date_key = ts_utc.date().isoformat()
        daily_buckets[date_key].append(sev)

    daily_trend = [
        DailySeverityPoint(
            date=date_key,
            average_severity=round(sum(day_sevs) / len(day_sevs), 2),
            entry_count=len(day_sevs),
        )
        for date_key, day_sevs in sorted(daily_buckets.items(), key=lambda item: item[0])
    ]

    return AnalyticsResponse(
        patient_id=patient_id,
        window_days=ANALYTICS_WINDOW_DAYS,
        total_entries=total_entries,
        average_severity=average_severity,
        highest_severity=highest_severity,
        daily_trend=daily_trend,
    )


def _bucket_start(day: date, interval: str) -> date:
    if interval == "weekly":
        return day - timedelta(days=day.weekday())  # ISO Monday start
    if interval == "monthly":
        return day.replace(day=1)
    return day


def _clean_description(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def get_advanced_patient_analytics(
    db: Session,
    patient_id: str,
    date_from: date,
    date_to: date,
    interval: str,
) -> AdvancedAnalyticsResponse:
    """Deterministic UTC-date analytics using bounded patient-specific queries."""
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end_exclusive = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    stmt = (
        select(SymptomLog)
        .where(SymptomLog.patient_id == patient_id, SymptomLog.timestamp >= start, SymptomLog.timestamp < end_exclusive)
        .order_by(SymptomLog.timestamp.asc(), SymptomLog.id.asc())
    )
    records = list(db.scalars(stmt).all())
    # SQLite may return naive datetimes even for timezone-enabled columns.
    records = [r for r in records if date_from <= _normalize_utc(r.timestamp).date() <= date_to]

    bucket_values: dict[date, list[int]] = defaultdict(list)
    category_values: dict[str, list[int]] = defaultdict(list)
    category_dates: dict[str, set[date]] = defaultdict(set)
    category_counts: dict[str, int] = defaultdict(int)
    description_values: dict[str, list[date]] = defaultdict(list)
    by_day: dict[date, list[int]] = defaultdict(list)
    for record in records:
        day = _normalize_utc(record.timestamp).date()
        bucket_values[_bucket_start(day, interval)].append(record.severity)
        category = record.category or "Uncategorized"
        category_values[category].append(record.severity)
        category_dates[category].add(day)
        category_counts[category] += 1
        description_values[_clean_description(record.symptom_description)].append(day)
        by_day[day].append(record.severity)

    trend = [
        AnalyticsBucket(period_start=key.isoformat(), average_severity=round(sum(values) / len(values), 2),
                        maximum_severity=max(values), entry_count=len(values))
        for key, values in sorted(bucket_values.items())
    ]
    category_rows = [
        CategoryAnalytics(category=key, entry_count=len(values), average_severity=round(sum(values) / len(values), 2))
        for key, values in sorted(category_values.items())
    ]

    recurring: list[RecurringSymptomPattern] = []
    for category, days in sorted(category_dates.items()):
        if len(days) >= RECURRING_DISTINCT_DATE_THRESHOLD:
            dates = sorted(d.isoformat() for d in days)
            recurring.append(RecurringSymptomPattern(
                pattern_type="category", label=category,
                occurrence_count=category_counts[category],
                distinct_dates=dates,
            ))
    for description, dates_seen in sorted(description_values.items()):
        distinct = sorted(set(dates_seen))
        if len(distinct) >= RECURRING_DISTINCT_DATE_THRESHOLD:
            recurring.append(RecurringSymptomPattern(
                pattern_type="description", label=description,
                occurrence_count=len(dates_seen), distinct_dates=[d.isoformat() for d in distinct],
            ))

    mood_stmt = select(DailyMoodSleepRecord).where(
        DailyMoodSleepRecord.patient_id == patient_id,
        DailyMoodSleepRecord.record_date >= date_from,
        DailyMoodSleepRecord.record_date <= date_to,
    )
    mood_by_day = {record.record_date: record for record in db.scalars(mood_stmt).all()}
    mood_groups: dict[str, list[int]] = defaultdict(list)
    sleep_groups: dict[str, list[int]] = defaultdict(list)
    for day, severities in by_day.items():
        record = mood_by_day.get(day)
        if record is None:
            continue
        mood_groups[f"{record.mood_rating} / 5"].extend(severities)
        hours = float(record.sleep_duration_hours)
        sleep_group = "Under 6 hours" if hours < 6 else "6 to under 7 hours" if hours < 7 else "7 to 9 hours" if hours <= 9 else "Over 9 hours"
        sleep_groups[sleep_group].extend(severities)

    def comparisons(groups: dict[str, list[int]], order: list[str]) -> list[SeverityComparison]:
        return [SeverityComparison(group=key, average_severity=round(sum(groups[key]) / len(groups[key]), 2),
                                   matching_symptom_entries=len(groups[key]))
                for key in order if groups.get(key)]

    return AdvancedAnalyticsResponse(
        patient_id=patient_id, date_from=date_from, date_to=date_to, interval=interval,
        total_entries=len(records),
        average_severity=round(sum(r.severity for r in records) / len(records), 2) if records else None,
        maximum_severity=max((r.severity for r in records), default=None),
        trend=trend, category_frequency=category_rows, category_severity=category_rows,
        recurring_patterns=recurring,
        severity_by_mood_rating=comparisons(mood_groups, [f"{n} / 5" for n in range(1, 6)]),
        severity_by_sleep_duration=comparisons(sleep_groups, ["Under 6 hours", "6 to under 7 hours", "7 to 9 hours", "Over 9 hours"]),
    )
