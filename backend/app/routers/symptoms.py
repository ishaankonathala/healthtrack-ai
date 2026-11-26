from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import SymptomLog
from backend.app.schemas import SymptomCreate, SymptomResponse, SymptomUpdate
from backend.app.services.symptom_service import (
    SymptomRecordNotFoundError,
    delete_symptom_record,
    get_symptom_history,
    update_symptom_record,
)
from backend.app.symptom_categories import SymptomCategory

router = APIRouter(prefix="/symptoms", tags=["symptoms"])


@router.post("", response_model=SymptomResponse, status_code=status.HTTP_201_CREATED)
def create_symptom(payload: SymptomCreate, db: Session = Depends(get_db)) -> SymptomLog:
    """Create a new symptom log entry."""
    record = SymptomLog(
        patient_id=payload.patient_id,
        symptom_description=payload.symptom_description,
        severity=payload.severity,
        category=payload.category.value,
        notes=payload.notes,
        possible_triggers=payload.possible_triggers,
        timestamp=payload.resolved_timestamp(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{patient_id}", response_model=list[SymptomResponse])
def get_patient_symptoms(
    patient_id: str,
    category: SymptomCategory | Literal["uncategorized"] | None = None,
    min_severity: int | None = Query(default=None, ge=1, le=10),
    max_severity: int | None = Query(default=None, ge=1, le=10),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
) -> list[SymptomLog]:
    """Retrieve patient history; optional query filters combine with AND."""
    cleaned_patient_id = patient_id.strip()
    if not cleaned_patient_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="patient_id must not be empty or whitespace-only",
        )
    if min_severity is not None and max_severity is not None and min_severity > max_severity:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="min_severity must be less than or equal to max_severity",
        )
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_from must be on or before date_to",
        )
    return get_symptom_history(
        db,
        cleaned_patient_id,
        category=category,
        min_severity=min_severity,
        max_severity=max_severity,
        date_from=date_from,
        date_to=date_to,
    )


@router.patch("/{patient_id}/{record_id}", response_model=SymptomResponse)
def patch_patient_symptom(
    patient_id: str,
    record_id: int,
    changes: SymptomUpdate,
    db: Session = Depends(get_db),
) -> SymptomLog:
    """Update a symptom only when it belongs to the path patient."""
    cleaned_patient_id = patient_id.strip()
    if not cleaned_patient_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="patient_id must not be empty or whitespace-only",
        )
    try:
        return update_symptom_record(db, cleaned_patient_id, record_id, changes)
    except SymptomRecordNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Symptom record not found.") from exc


@router.delete("/{patient_id}/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_patient_symptom(patient_id: str, record_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete a symptom only when it belongs to the path patient."""
    cleaned_patient_id = patient_id.strip()
    if not cleaned_patient_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="patient_id must not be empty or whitespace-only",
        )
    try:
        delete_symptom_record(db, cleaned_patient_id, record_id)
    except SymptomRecordNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Symptom record not found.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
