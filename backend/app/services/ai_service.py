import os
from datetime import timezone

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy import select
from sqlalchemy.orm import Session

import backend.app.config  # noqa: F401
from backend.app.models import SymptomLog
from backend.app.schemas import AISummaryResponse

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
NON_DIAGNOSTIC_DISCLAIMER = (
    "Disclaimer: This summary is generated for informational purposes to support "
    "doctor-visit discussions. It is not a medical diagnosis, treatment recommendation, "
    "or substitute for professional medical advice."
)

SUMMARY_SYSTEM_PROMPT = """You are a clinical documentation assistant helping a patient prepare for a doctor visit.
Your role is strictly summarization — NOT diagnosis or treatment.

Strict Safety Rules:
1. NEVER diagnose diseases or medical conditions.
2. NEVER recommend medications, dosages, or treatments.
3. NEVER invent symptoms, dates, statistics, or medical history not present in the provided records.
4. Clearly separate **Recorded Facts** (exact entries, dates, and severities from the log) from **AI-Generated Observations** (patterns such as repeated symptoms or severity trends supported strictly by the data).
5. End with a clear disclaimer stating that this summary is not a medical diagnosis.

Required Sections in Your Response:
- **Patient & Log Overview**: Patient ID and total number of recorded symptom entries.
- **Recorded Facts (Chronological History)**: Chronological overview listing the recorded symptoms, their timestamps (UTC), and severities (1-10).
- **AI-Generated Observations**: Repeated symptoms (if any) and severity patterns supported strictly by the recorded data.
- **Concise Doctor-Visit Summary**: A brief, readable paragraph the patient can share with a healthcare professional.
- **Disclaimer**: Explicit statement that this is not a medical diagnosis."""

SUMMARY_HUMAN_PROMPT = """Patient ID: {patient_id}
Total Recorded Entries: {entry_count}

Chronological Symptom Records:
{symptom_history}

Please generate the structured doctor-visit summary following all safety rules."""


class MissingAPIKeyError(Exception):
    """Raised when GEMINI_API_KEY is missing from environment configuration."""


class NoSymptomRecordsError(Exception):
    """Raised when a patient has no symptom records to summarize."""


class AIServiceError(Exception):
    """Raised when the AI provider fails to generate a summary."""


def get_gemini_config() -> tuple[str, str]:
    """Read Gemini API key and model from environment variables."""
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise MissingAPIKeyError(
            "GEMINI_API_KEY is not configured. Please set it in the .env file."
        )
    model = (os.getenv("GEMINI_MODEL") or "").strip() or DEFAULT_GEMINI_MODEL
    return api_key, model


def create_llm(api_key: str, model: str) -> Runnable:
    """Instantiate the LangChain Gemini chat model."""
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=0.2,
    )


def format_symptom_history(records: list[SymptomLog]) -> str:
    """Format SymptomLog records chronologically for the LLM prompt."""
    lines: list[str] = []
    for idx, record in enumerate(records, start=1):
        ts = record.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        ts_str = ts.strftime("%Y-%m-%d %H:%M UTC")
        lines.append(
            f"{idx}. [{ts_str}] Severity {record.severity}/10 — {record.symptom_description}"
        )
    return "\n".join(lines)


def generate_doctor_visit_summary(db: Session, patient_id: str) -> AISummaryResponse:
    """Fetch patient symptom records and generate a non-diagnostic visit summary."""
    stmt = (
        select(SymptomLog)
        .where(SymptomLog.patient_id == patient_id)
        .order_by(SymptomLog.timestamp.asc(), SymptomLog.id.asc())
    )
    records = list(db.scalars(stmt).all())
    if not records:
        raise NoSymptomRecordsError(
            f"No symptom records found for patient '{patient_id}'."
        )

    api_key, model = get_gemini_config()
    symptom_history = format_symptom_history(records)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SUMMARY_SYSTEM_PROMPT),
            ("human", SUMMARY_HUMAN_PROMPT),
        ]
    )
    llm = create_llm(api_key=api_key, model=model)
    chain = prompt | llm | StrOutputParser()

    try:
        summary_text = chain.invoke(
            {
                "patient_id": patient_id,
                "entry_count": len(records),
                "symptom_history": symptom_history,
            }
        )
    except Exception as exc:
        raise AIServiceError("Failed to generate AI summary from Gemini.") from exc

    return AISummaryResponse(
        patient_id=patient_id,
        entry_count=len(records),
        model=model,
        summary=summary_text.strip(),
        disclaimer=NON_DIAGNOSTIC_DISCLAIMER,
    )
