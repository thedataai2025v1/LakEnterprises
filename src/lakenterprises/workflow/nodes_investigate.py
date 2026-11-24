"""Document investigation and knowledge retrieval graph nodes (P10-3)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from lakenterprises.agents.document_analyst import DocumentAnalysisAgent
from lakenterprises.agents.knowledge_retriever import KnowledgeRetrievalAgent
from lakenterprises.workflow.state import WorkflowState

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def document_analyst_node(state: WorkflowState) -> WorkflowState:
    """Investigation node analyzing input documents and extracting structured terms."""
    logger.info(
        "Executing document_analyst_node for process %s", state.get("process_id")
    )
    state = dict(state)

    payload = state.get("input_payload", {})
    doc_text = payload.get("document_text") or state.get("goal", "")
    doc_id = payload.get("document_id", "DOC-PROC-01")
    doc_type = payload.get("doc_type", "contract")

    analyst = DocumentAnalysisAgent()
    analysis = analyst.analyze_document(
        document_text=doc_text,
        document_id=doc_id,
        doc_type=doc_type,
        context=payload,
    )
    analysis_dict = analysis.model_dump()

    state["document_analysis"] = analysis_dict
    state["current_step"] = "document_analyst"
    state["active_node"] = "document_analyst"

    routing_history = list(state.get("routing_history", []))
    routing_history.append("document_analyst")
    state["routing_history"] = routing_history

    agent_outputs = dict(state.get("agent_outputs", {}))
    agent_outputs["document_analyst"] = analysis_dict
    state["agent_outputs"] = agent_outputs

    collected_documents = list(state.get("collected_documents", []))
    summary = (
        ", ".join(analysis.key_findings)
        if analysis.key_findings
        else "Document analyzed"
    )
    collected_documents.append(
        {"document_id": doc_id, "doc_type": doc_type, "summary": summary}
    )
    state["collected_documents"] = collected_documents

    history = list(state.get("history", []))
    history.append(
        {
            "step": "document_analyst",
            "timestamp": _now_iso(),
            "status": "analyzed",
            "details": f"Extracted entities: {analysis.extracted_entities}, {len(analysis.risk_signals)} risk signals",
        }
    )
    state["history"] = history
    return state


def knowledge_retriever_node(state: WorkflowState) -> WorkflowState:
    """Investigation node pulling grounded evidence and verified citations."""
    logger.info(
        "Executing knowledge_retriever_node for process %s", state.get("process_id")
    )
    state = dict(state)

    payload = state.get("input_payload", {})
    query = payload.get("query") or state.get("goal", "")

    retriever = KnowledgeRetrievalAgent()
    knowledge = retriever.retrieve_knowledge(query=query, context=payload)
    knowledge_dict = knowledge.model_dump()

    state["knowledge"] = knowledge_dict
    state["current_step"] = "knowledge_retriever"
    state["active_node"] = "knowledge_retriever"

    routing_history = list(state.get("routing_history", []))
    routing_history.append("knowledge_retriever")
    state["routing_history"] = routing_history

    agent_outputs = dict(state.get("agent_outputs", {}))
    agent_outputs["knowledge_retriever"] = knowledge_dict
    state["agent_outputs"] = agent_outputs

    # Merge unique citations
    current_citations = list(state.get("citations", []))
    for c in knowledge.citations:
        if c not in current_citations:
            current_citations.append(c)
    state["citations"] = current_citations

    history = list(state.get("history", []))
    history.append(
        {
            "step": "knowledge_retriever",
            "timestamp": _now_iso(),
            "status": "retrieved",
            "details": f"Retrieved {len(knowledge.facts)} facts, citations: {knowledge.citations}",
        }
    )
    state["history"] = history
    return state
