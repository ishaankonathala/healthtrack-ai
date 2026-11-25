from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas import AnalyticsResponse
from backend.app.services.analytics_service import get_patient_analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


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
