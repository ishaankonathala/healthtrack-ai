from fastapi import APIRouter, HTTPException, status

from backend.app.rag.chains import (
    RAGAuthError,
    RAGProviderError,
    RAGQuotaError,
    RAGTimeoutError,
    answer_health_question,
)
from backend.app.schemas import RAGAskRequest, RAGAskResponse

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/ask", response_model=RAGAskResponse)
def ask_health_assistant(payload: RAGAskRequest) -> RAGAskResponse:
    """Answer a general health education question grounded in curated MedlinePlus docs."""
    try:
        return answer_health_question(question=payload.question)
    except RAGQuotaError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    except RAGAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except RAGTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        ) from exc
    except RAGProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
