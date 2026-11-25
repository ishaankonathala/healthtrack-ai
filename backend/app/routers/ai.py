from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas import AISummaryResponse
from backend.app.services.ai_service import (
    AIServiceError,
    MissingAPIKeyError,
    NoSymptomRecordsError,
    generate_doctor_visit_summary,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/summary/{patient_id}", response_model=AISummaryResponse)
def create_ai_summary(patient_id: str, db: Session = Depends(get_db)) -> AISummaryResponse:
    """Generate a non-diagnostic doctor-visit summary for a patient's symptom history."""
    cleaned_patient_id = patient_id.strip()
    if not cleaned_patient_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="patient_id must not be empty or whitespace-only",
        )

    try:
        return generate_doctor_visit_summary(db=db, patient_id=cleaned_patient_id)
    except NoSymptomRecordsError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MissingAPIKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
