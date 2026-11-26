"""Bounded adapter from an explicit question to the existing curated MedlinePlus RAG chain."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.rag.chains import INSUFFICIENT_INFO_ANSWER, answer_health_question
from backend.app.rag.retriever import DEFAULT_TOP_K
from backend.app.schemas import HealthIntelligenceSource, MedicalKnowledgeResult


class MedicalKnowledgeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("question must not be blank")
        return cleaned


def analyze_medical_knowledge(data: MedicalKnowledgeInput) -> MedicalKnowledgeResult:
    """Answer one explicit educational question; the caller supplies no patient context."""
    try:
        response = answer_health_question(question=data.question, top_k=DEFAULT_TOP_K)
        sources = [
            HealthIntelligenceSource(title=source.title, url=source.url)
            for source in response.sources[:DEFAULT_TOP_K]
        ]
        if not sources:
            return MedicalKnowledgeResult(
                agent_status="no_relevant_information",
                question=data.question,
                answer=INSUFFICIENT_INFO_ANSWER,
                warnings=["No relevant reference passed the existing RAG relevance threshold."],
                limitations=["The curated collection currently covers headache, fever, dehydration, and the common cold."],
            )
        return MedicalKnowledgeResult(
            agent_status="complete",
            question=data.question,
            answer=response.answer[:4000],
            sources=sources,
            limitations=[
                "This is general educational information from curated references, not a patient-specific conclusion.",
                "The existing retriever returns only documents above its relevance threshold and does not expose relevance scores.",
            ],
        )
    except Exception:
        # Provider, retrieval and output-shape failures remain isolated from patient analysis.
        return MedicalKnowledgeResult(
            agent_status="unavailable",
            question=data.question,
            answer="General educational information is temporarily unavailable.",
            warnings=["The curated health-education service could not complete this request."],
            limitations=["Patient analysis continues independently of educational retrieval."],
        )
