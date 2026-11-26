from functools import partial

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from backend.app.health_intelligence.nodes import (
    gather_patient_evidence,
    health_report_agent,
    lifestyle_analysis,
    medical_knowledge,
    symptom_analysis,
    validate_report,
    validate_request,
)
from backend.app.health_intelligence.state import HealthIntelligenceState

HEALTH_INTELLIGENCE_NODE_SEQUENCE = (
    "validate_request",
    "gather_patient_evidence",
    "symptom_analysis",
    "lifestyle_analysis",
    "health_report_agent",
    "validate_report",
)


def build_health_intelligence_graph(db: Session):
    """Compile a fixed graph; its only database capability is bounded evidence gathering."""
    workflow = StateGraph(HealthIntelligenceState)
    workflow.add_node("validate_request", validate_request)
    workflow.add_node("gather_patient_evidence", partial(gather_patient_evidence, db=db))
    workflow.add_node("symptom_analysis", symptom_analysis)
    workflow.add_node("lifestyle_analysis", lifestyle_analysis)
    workflow.add_node("medical_knowledge", medical_knowledge)
    workflow.add_node("health_report_agent", health_report_agent)
    workflow.add_node("validate_report", validate_report)
    workflow.add_edge(START, HEALTH_INTELLIGENCE_NODE_SEQUENCE[0])
    for left, right in zip(HEALTH_INTELLIGENCE_NODE_SEQUENCE, HEALTH_INTELLIGENCE_NODE_SEQUENCE[1:]):
        if left != "lifestyle_analysis":
            workflow.add_edge(left, right)
    workflow.add_conditional_edges(
        "lifestyle_analysis",
        lambda state: "medical_knowledge" if state.get("educational_question") else "health_report_agent",
        {
            "medical_knowledge": "medical_knowledge",
            "health_report_agent": "health_report_agent",
        },
    )
    workflow.add_edge("medical_knowledge", "health_report_agent")
    workflow.add_edge(HEALTH_INTELLIGENCE_NODE_SEQUENCE[-1], END)
    return workflow.compile()
