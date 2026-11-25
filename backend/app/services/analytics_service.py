from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import SymptomLog
from backend.app.schemas import AnalyticsResponse, DailySeverityPoint

ANALYTICS_WINDOW_DAYS = 30


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
