from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas import MoodSleepCreate, MoodSleepResponse, MoodSleepUpdate
from backend.app.services.mood_sleep_service import (
    DuplicateDailyRecordError,
    MoodSleepRecordNotFoundError,
    create_mood_sleep_record,
    delete_mood_sleep_record,
    get_mood_sleep_history,
    update_mood_sleep_record,
)

router = APIRouter(prefix="/mood-sleep", tags=["mood-and-sleep"])


def _clean_patient_id(patient_id: str) -> str:
    cleaned = patient_id.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="patient_id must not be empty or whitespace-only",
        )
    return cleaned


@router.post("", response_model=MoodSleepResponse, status_code=status.HTTP_201_CREATED)
def create_record(payload: MoodSleepCreate, db: Session = Depends(get_db)) -> MoodSleepResponse:
    """Create the single daily mood and sleep record for a patient and UTC date."""
    try:
        return create_mood_sleep_record(db=db, payload=payload)
    except DuplicateDailyRecordError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A mood and sleep record already exists for this patient and date.",
        ) from exc


@router.get("/{patient_id}", response_model=list[MoodSleepResponse])
def read_history(patient_id: str, db: Session = Depends(get_db)) -> list[MoodSleepResponse]:
    """Retrieve one patient's check-ins ordered by UTC calendar date ascending."""
    return get_mood_sleep_history(db=db, patient_id=_clean_patient_id(patient_id))


@router.patch("/{patient_id}/{record_id}", response_model=MoodSleepResponse)
def update_record(
    patient_id: str,
    record_id: int,
    changes: MoodSleepUpdate,
    db: Session = Depends(get_db),
) -> MoodSleepResponse:
    """Update supplied fields on a record owned by the path patient."""
    cleaned_patient_id = _clean_patient_id(patient_id)
    try:
        return update_mood_sleep_record(
            db=db,
            patient_id=cleaned_patient_id,
            record_id=record_id,
            changes=changes,
        )
    except MoodSleepRecordNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mood and sleep record not found.") from exc
    except DuplicateDailyRecordError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A mood and sleep record already exists for this patient and date.",
        ) from exc


@router.delete("/{patient_id}/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_record(patient_id: str, record_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete a record only when it belongs to the specified patient."""
    try:
        delete_mood_sleep_record(
            db=db,
            patient_id=_clean_patient_id(patient_id),
            record_id=record_id,
        )
    except MoodSleepRecordNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mood and sleep record not found.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
