from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import SymptomLog
from backend.app.schemas import SymptomCreate, SymptomResponse

router = APIRouter(prefix="/symptoms", tags=["symptoms"])


@router.post("", response_model=SymptomResponse, status_code=status.HTTP_201_CREATED)
def create_symptom(payload: SymptomCreate, db: Session = Depends(get_db)) -> SymptomLog:
    """Create a new symptom log entry."""
    record = SymptomLog(
        patient_id=payload.patient_id,
        symptom_description=payload.symptom_description,
        severity=payload.severity,
        timestamp=payload.resolved_timestamp(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{patient_id}", response_model=list[SymptomResponse])
def get_patient_symptoms(patient_id: str, db: Session = Depends(get_db)) -> list[SymptomLog]:
    """Retrieve all symptom logs for a patient sorted by timestamp ascending."""
    cleaned_patient_id = patient_id.strip()
    if not cleaned_patient_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="patient_id must not be empty or whitespace-only",
        )

    stmt = (
        select(SymptomLog)
        .where(SymptomLog.patient_id == cleaned_patient_id)
        .order_by(SymptomLog.timestamp.asc(), SymptomLog.id.asc())
    )
    return list(db.scalars(stmt).all())
