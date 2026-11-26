from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.health_intelligence.graph import build_health_intelligence_graph
from backend.app.health_intelligence.state import HealthIntelligenceState
from backend.app.schemas import (
    AISummaryResponse,
    HealthIntelligenceRequest,
    HealthIntelligenceResponse,
)
from backend.app.services.ai_service import (
    AIServiceError,
    MissingAPIKeyError,
    NoSymptomRecordsError,
    generate_doctor_visit_summary,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/health-intelligence/{patient_id}", response_model=HealthIntelligenceResponse)
def create_health_intelligence_report(
    patient_id: Annotated[str, Path(min_length=1, max_length=100)],
    payload: HealthIntelligenceRequest,
    db: Session = Depends(get_db),
) -> HealthIntelligenceResponse:
    """Explicitly invoke a bounded, read-only deterministic analysis and report graph."""
    cleaned_patient_id = patient_id.strip()
    if not cleaned_patient_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="patient_id must not be empty or whitespace-only",
        )
    request_id = str(uuid4())
    initial_state: HealthIntelligenceState = {
        "patient_id": cleaned_patient_id,
        "date_from": payload.date_from,
        "date_to": payload.date_to,
        "request_id": request_id,
        "analytics": None,
        "symptom_evidence": None,
        "symptom_analysis_result": None,
        "lifestyle_evidence": None,
        "lifestyle_analysis_input": None,
        "lifestyle_analysis_result": None,
        "educational_question": payload.educational_question,
        "medical_knowledge_result": None,
        "warnings": [],
        "report": None,
        "execution_status": "pending",
        "error_code": None,
    }
    try:
        result = build_health_intelligence_graph(db).invoke(initial_state)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health intelligence workflow failed.",
        ) from exc

    if (
        result.get("execution_status") != "succeeded"
        or result.get("report") is None
        or result.get("symptom_analysis_result") is None
        or result.get("lifestyle_analysis_result") is None
    ):
        error_code = result.get("error_code")
        if error_code == "invalid_request":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=result.get("warnings", []))
        if error_code == "missing_api_key":
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Gemini is not configured.")
        if error_code in {"report_generation_failed", "invalid_report"}:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="The health intelligence report could not be generated.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Health evidence could not be processed.")

    return HealthIntelligenceResponse(
        request_id=request_id,
        patient_id=cleaned_patient_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        symptom_analysis=result["symptom_analysis_result"],
        lifestyle_analysis=result["lifestyle_analysis_result"],
        medical_knowledge=result.get("medical_knowledge_result"),
        report=result["report"],
        warnings=result.get("warnings", []),
    )


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
