import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=False)

DEFAULT_API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT_SECONDS = 5
AI_REQUEST_TIMEOUT_SECONDS = 30


def format_error_detail(response: requests.Response) -> str:
    """Extract a readable validation or error message from a FastAPI response."""
    try:
        payload = response.json()
    except ValueError:
        return f"Request failed with status {response.status_code}."

    detail = payload.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        messages = []
        for item in detail:
            if isinstance(item, dict):
                loc = ".".join(str(part) for part in item.get("loc", []) if part != "body")
                msg = item.get("msg", "Invalid value")
                messages.append(f"{loc}: {msg}" if loc else msg)
            else:
                messages.append(str(item))
        if messages:
            return "; ".join(messages)
    return f"Request failed with status {response.status_code}."


def format_timestamp(raw_ts: str) -> str:
    """Format an ISO-8601 timestamp for display."""
    try:
        dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except ValueError:
        return raw_ts


def check_api_health(api_base_url: str) -> bool:
    """Check whether the FastAPI backend is reachable."""
    try:
        response = requests.get(f"{api_base_url}/health", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


def submit_symptom(
    api_base_url: str,
    patient_id: str,
    symptom_description: str,
    severity: int,
) -> tuple[bool, str]:
    """Submit a symptom log to POST /symptoms."""
    try:
        response = requests.post(
            f"{api_base_url}/symptoms",
            json={
                "patient_id": patient_id,
                "symptom_description": symptom_description,
                "severity": severity,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.ConnectionError:
        return False, f"Could not connect to the API at {api_base_url}. Is the backend running?"
    except requests.Timeout:
        return False, "The request to the API timed out. Please try again."
    except requests.RequestException as exc:
        return False, f"Unexpected network error: {exc}"

    if response.status_code == 201:
        return True, "Symptom logged successfully."
    return False, format_error_detail(response)


def fetch_patient_history(api_base_url: str, patient_id: str) -> tuple[list[dict] | None, str | None]:
    """Fetch symptom records for a patient from GET /symptoms/{patient_id}."""
    try:
        response = requests.get(
            f"{api_base_url}/symptoms/{patient_id}",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.ConnectionError:
        return None, f"Could not connect to the API at {api_base_url}. Is the backend running?"
    except requests.Timeout:
        return None, "Timed out while fetching patient history."
    except requests.RequestException as exc:
        return None, f"Unexpected network error: {exc}"

    if response.status_code == 200:
        records = response.json()
        # Ensure oldest-first ordering with latest entries at the bottom
        records.sort(key=lambda item: item.get("timestamp", ""))
        return records, None
    return None, format_error_detail(response)


def fetch_patient_analytics(api_base_url: str, patient_id: str) -> tuple[dict | None, str | None]:
    """Fetch 30-day symptom analytics for a patient from GET /analytics/{patient_id}."""
    try:
        response = requests.get(
            f"{api_base_url}/analytics/{patient_id}",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.ConnectionError:
        return None, f"Could not connect to the API at {api_base_url}. Is the backend running?"
    except requests.Timeout:
        return None, "Timed out while fetching patient analytics."
    except requests.RequestException as exc:
        return None, f"Unexpected network error: {exc}"

    if response.status_code == 200:
        return response.json(), None
    return None, format_error_detail(response)


def render_analytics_section(api_base_url: str, patient_id: str) -> None:
    """Render 30-day symptom analytics metrics and daily trend chart."""
    st.subheader("Symptom Analytics (Last 30 Days)")

    analytics, error_message = fetch_patient_analytics(api_base_url, patient_id)
    if error_message:
        st.error(error_message)
        return

    if not analytics or analytics.get("total_entries", 0) == 0:
        st.info(f"No symptom entries recorded in the last 30 days for `{patient_id}`.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Entries", analytics["total_entries"])
    avg_sev = analytics.get("average_severity")
    col2.metric("Average Severity", f"{avg_sev:.2f}" if avg_sev is not None else "N/A")
    high_sev = analytics.get("highest_severity")
    col3.metric("Highest Severity", f"{high_sev}/10" if high_sev is not None else "N/A")

    daily_trend = analytics.get("daily_trend", [])
    if daily_trend:
        trend_df = pd.DataFrame(daily_trend)
        trend_df = trend_df.rename(
            columns={
                "date": "Date",
                "average_severity": "Average Severity",
                "entry_count": "Entries",
            }
        )
        fig = px.line(
            trend_df,
            x="Date",
            y="Average Severity",
            markers=True,
            hover_data=["Entries"],
            title="Daily Average Severity (Last 30 Days)",
        )
        fig.update_layout(
            yaxis=dict(range=[0.5, 10.5], dtick=1, title="Average Severity (1–10)"),
            xaxis=dict(title="Date", type="category"),
            margin=dict(l=20, r=20, t=45, b=20),
        )
        st.plotly_chart(fig, width="stretch")


def generate_ai_summary(api_base_url: str, patient_id: str) -> tuple[dict | None, str | None]:
    """Request an AI doctor-visit summary from POST /ai/summary/{patient_id}."""
    try:
        response = requests.post(
            f"{api_base_url}/ai/summary/{patient_id}",
            timeout=AI_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.ConnectionError:
        return None, f"Could not connect to the API at {api_base_url}. Is the backend running?"
    except requests.Timeout:
        return None, "Timed out while generating the AI summary. Please try again."
    except requests.RequestException as exc:
        return None, f"Unexpected network error: {exc}"

    if response.status_code == 200:
        return response.json(), None
    return None, format_error_detail(response)


def render_ai_summary_section(api_base_url: str, patient_id: str) -> None:
    """Render the on-demand AI Doctor-Visit Summary section."""
    st.subheader("AI Doctor-Visit Summary")
    st.caption("Generate a non-diagnostic summary of recorded symptoms to share with your clinician.")

    summaries_by_patient = st.session_state.setdefault("ai_summaries", {})

    if st.button("Generate Summary", type="primary", key=f"generate_summary_{patient_id}"):
        with st.spinner("Generating doctor-visit summary..."):
            summary_data, error_message = generate_ai_summary(api_base_url, patient_id)
        if error_message:
            st.error(error_message)
        elif summary_data:
            summaries_by_patient[patient_id] = summary_data

    cached_summary = summaries_by_patient.get(patient_id)
    if cached_summary:
        with st.container(border=True):
            st.markdown(cached_summary["summary"])
        st.caption(
            f"Based on {cached_summary['entry_count']} recorded entries • "
            f"Model: {cached_summary['model']} • {cached_summary['disclaimer']}"
        )


def ask_rag_assistant(api_base_url: str, question: str) -> tuple[dict | None, str | None]:
    """Send a health education question to POST /rag/ask."""
    try:
        response = requests.post(
            f"{api_base_url}/rag/ask",
            json={"question": question},
            timeout=AI_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.ConnectionError:
        return None, f"Could not connect to the API at {api_base_url}. Is the backend running?"
    except requests.Timeout:
        return None, "Timed out while generating an answer. Please try again."
    except requests.RequestException as exc:
        return None, f"Unexpected network error: {exc}"

    if response.status_code == 200:
        return response.json(), None
    return None, format_error_detail(response)


def render_rag_assistant_section(api_base_url: str) -> None:
    """Render the AI Health Education Assistant section."""
    st.subheader("AI Health Education Assistant")
    st.caption(
        "Ask general health education questions grounded in curated MedlinePlus resources. "
        "This is not a diagnostic tool."
    )

    question_input = st.text_input(
        "Health Education Question",
        placeholder="e.g. What are common signs of dehydration?",
        key="rag_question_input",
    )

    if st.button("Ask", type="primary", key="rag_ask_button"):
        cleaned_question = question_input.strip()
        if not cleaned_question:
            st.error("Please enter a question before clicking Ask.")
        else:
            with st.spinner("Searching health education resources and generating answer..."):
                rag_data, error_message = ask_rag_assistant(api_base_url, cleaned_question)
            if error_message:
                st.error(error_message)
            elif rag_data:
                st.session_state["rag_last_response"] = rag_data

    last_response = st.session_state.get("rag_last_response")
    if last_response:
        with st.container(border=True):
            st.markdown(last_response["answer"])
        sources = last_response.get("sources", [])
        if sources:
            st.markdown("**Sources**")
            for src in sources:
                title = src.get("title", "Source")
                url = src.get("url", "")
                if url:
                    st.markdown(f"- [{title}]({url})")
                else:
                    st.markdown(f"- {title}")
        else:
            st.info("No matching knowledge base sources were cited for this response.")


def main() -> None:
    st.set_page_config(
        page_title="HealthTrack AI",
        page_icon="🩺",
        layout="centered",
    )

    st.title("HealthTrack AI")
    st.caption("Patient Symptom Logging & History")

    with st.sidebar:
        st.header("Connection")
        api_url_input = st.text_input("API Base URL", value=DEFAULT_API_BASE_URL)
        api_base_url = (api_url_input.strip() or DEFAULT_API_BASE_URL).rstrip("/")
        if check_api_health(api_base_url):
            st.success("API connected")
        else:
            st.warning("API unreachable")

    patient_id_input = st.text_input(
        "Patient ID",
        placeholder="e.g. patient-001",
    )
    cleaned_patient_id = patient_id_input.strip()

    st.subheader("Log a Symptom")
    with st.form("symptom_submission_form", clear_on_submit=True):
        symptom_description = st.text_area(
            "Symptom Description",
            placeholder="Describe the symptom...",
            height=100,
        )
        severity = st.slider(
            "Severity (1–10)",
            min_value=1,
            max_value=10,
            value=5,
        )
        submitted = st.form_submit_button("Submit Symptom", type="primary", width="stretch")

    if submitted:
        if not cleaned_patient_id:
            st.error("Please enter a Patient ID before submitting.")
        elif not symptom_description.strip():
            st.error("Symptom description cannot be empty or whitespace-only.")
        else:
            ok, message = submit_symptom(
                api_base_url=api_base_url,
                patient_id=cleaned_patient_id,
                symptom_description=symptom_description.strip(),
                severity=severity,
            )
            if ok:
                st.success(message)
            else:
                st.error(message)

    st.divider()
    st.subheader("Patient History")

    if not cleaned_patient_id:
        st.info("Enter a Patient ID above to view symptom history, analytics, and visit summaries.")
    else:
        records, error_message = fetch_patient_history(api_base_url, cleaned_patient_id)
        if error_message:
            st.error(error_message)
        elif not records:
            st.info(f"No symptom records found for `{cleaned_patient_id}`.")
        else:
            table_rows = [
                {
                    "Timestamp": format_timestamp(record["timestamp"]),
                    "Symptom Description": record["symptom_description"],
                    "Severity": record["severity"],
                }
                for record in records
            ]
            df = pd.DataFrame(table_rows)
            st.dataframe(df, hide_index=True, width="stretch")

        st.divider()
        render_analytics_section(api_base_url, cleaned_patient_id)

        st.divider()
        render_ai_summary_section(api_base_url, cleaned_patient_id)

    st.divider()
    render_rag_assistant_section(api_base_url)


if __name__ == "__main__":
    main()
