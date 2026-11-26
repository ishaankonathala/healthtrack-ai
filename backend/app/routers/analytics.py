from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas import AdvancedAnalyticsResponse, AnalyticsResponse
from backend.app.services.analytics_service import get_advanced_patient_analytics, get_patient_analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/{patient_id}/advanced", response_model=AdvancedAnalyticsResponse)
def read_advanced_patient_analytics(
    patient_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
    interval: Literal["daily", "weekly", "monthly"] = "daily",
    db: Session = Depends(get_db),
) -> AdvancedAnalyticsResponse:
    """Detailed date-bounded analytics; date bounds are inclusive UTC calendar dates."""
    cleaned_patient_id = patient_id.strip()
    if not cleaned_patient_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="patient_id must not be empty or whitespace-only")
    today = datetime.now(timezone.utc).date()
    resolved_to = date_to or today
    resolved_from = date_from or (resolved_to - timedelta(days=29))
    if resolved_from > resolved_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="date_from must be on or before date_to")
    if (resolved_to - resolved_from).days > 3660:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Date range cannot exceed 10 years")
    return get_advanced_patient_analytics(db, cleaned_patient_id, resolved_from, resolved_to, interval)


@router.get("/{patient_id}", response_model=AnalyticsResponse)
def read_patient_analytics(patient_id: str, db: Session = Depends(get_db)) -> AnalyticsResponse:
    """Retrieve 30-day symptom analytics for a patient."""
    cleaned_patient_id = patient_id.strip()
    if not cleaned_patient_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="patient_id must not be empty or whitespace-only",
        )

    return get_patient_analytics(db=db, patient_id=cleaned_patient_id)
