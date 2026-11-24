"""LangGraph-based multi-agent research pipeline for the LakEnterprises platform.

Implements a StateGraph with 8 nodes that orchestrates query analysis,
decomposition, retrieval, verification, synthesis, answer generation,
logging, and finalization.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models import BaseLanguageModel
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    """Complete state carried through every node of the research pipeline."""

    query: str
    analysis: dict  # complexity, entities, time_ranges, sensitive_topics
    sub_questions: list[dict]  # each: {question, strategy, evidence, verified}
    evidence: list[dict]  # merged evidence with source, text, verification_status
    verification_ratio: float
    answer: str
    citations: list[str]
    error: str | None
    metadata: dict


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


@dataclass
class Response:
    """Return value of a completed pipeline run."""

    answer: str
    citations: list[str]
    metadata: dict = field(default_factory=dict)
    error: str | None = None


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


def _safe_node(func: Any, name: str):
    """Wrap a node function so exceptions are caught and stored in state."""

    def wrapper(state: AgentState) -> AgentState:
        try:
            result = func(state)
            return result
        except Exception as exc:
            logger.exception("Node %s raised %s", name, exc)
            state = state.copy() if isinstance(state, dict) else dict(state)
            state["error"] = f"{name}: {exc}"
            return state

    return wrapper


# -- Node 1: analyze -------------------------------------------------------


def analyze_node(state: AgentState) -> AgentState:
    """Analyze the user query.

    Determines complexity, extracts entities, time ranges, and detects
    sensitive topics using simple heuristics (LLM-based classification
    will be plugged in later).
    """
    state = dict(state)
    query = state["query"]

    # Heuristic complexity
    word_count = len(query.split())
    if word_count <= 15 or query.count("?") == 1:
        complexity = "simple"
    elif word_count <= 40 or query.count("?") <= 3:
        complexity = "moderate"
    else:
        complexity = "complex"

    # Entity extraction (placeholder – named-entity patterns)
    entities: list[str] = []
    for token in query.replace(",", " ").replace(".", " ").replace("?", " ").split():
        if token.isupper() and len(token) >= 3:
            entities.append(token)

    # Time-range detection (placeholder – recognises year tokens)
    import re

    time_ranges: list[str] = re.findall(r"\b(19|20)\d{2}\b", query)

    # Sensitive-topic detection (placeholder keyword list)
    sensitive_keywords = {
        "salary",
        "income",
        "salary",
        "earnings",
        "ssn",
        "social security",
        "credit card",
        "password",
        "medical",
        "health record",
    }
    sensitive_topics: list[str] = [
        kw for kw in sensitive_keywords if kw in query.lower()
    ]

    state["analysis"] = {
        "complexity": complexity,
        "entities": entities,
        "time_ranges": time_ranges,
        "sensitive_topics": sensitive_topics,
    }
    return state


# -- Node 2: decompose -----------------------------------------------------


def decompose_node(state: AgentState) -> AgentState:
    """Break the query into sub-questions and assign a retrieval strategy.

    For moderate/complex queries the LLM would normally split the question;
    here we create a single sub-question with a strategy based on keywords.
    """
    state = dict(state)
    query = state["query"]
    analysis = state.get("analysis", {})

    # Decide default strategy from keyword heuristics
    sql_keywords = {"count", "total", "average", "sum", "list all", "how many"}
    graph_keywords = {
        "related",
        "connected",
        "relationship",
        "network",
        "link",
    }

    query_lower = query.lower()

    if sql_keywords & {t.lower() for t in query_lower.split()} or any(
        kw in query_lower for kw in sql_keywords
    ):
        strategy = "sql"
    elif graph_keywords & {t.lower() for t in query_lower.split()} or any(
        kw in query_lower for kw in graph_keywords
    ):
        strategy = "graph"
    else:
        strategy = "vector"

    complexity = analysis.get("complexity", "moderate")

    if complexity == "complex":
        sub_questions: list[dict] = [
            {
                "question": query,
                "strategy": "hybrid",
                "evidence": [],
                "verified": False,
            },
        ]
    else:
        sub_questions = [
            {
                "question": query,
                "strategy": strategy,
                "evidence": [],
                "verified": False,
            },
        ]

    state["sub_questions"] = sub_questions
    return state


# -- Node 3: retrieve ------------------------------------------------------


def retrieve_node(state: AgentState) -> AgentState:
    """Call the appropriate retriever for each sub-question.

    Placeholder: returns empty evidence lists with the sub-question text
    as the source placeholder.
    """
    state = dict(state)
    sub_questions = state.get("sub_questions", [])

    # If decompose was skipped (simple query), create a default sub-question
    if not sub_questions:
        sub_questions = [
            {
                "question": state["query"],
                "strategy": "vector",
                "evidence": [],
                "verified": False,
            }
        ]

    for sq in sub_questions:
        # Placeholder retriever – real implementations go here
        sq["evidence"] = [
            {
                "source": "placeholder",
                "text": f"[Retrieved evidence for: {sq['question']}] "
                f"(strategy={sq['strategy']})",
                "verification_status": "unverified",
            }
        ]

    state["sub_questions"] = sub_questions
    return state


# -- Node 4: verify --------------------------------------------------------


def verify_node(state: AgentState) -> AgentState:
    """Cross-check evidence and mark each piece as verified/unverified/contradictory.

    Computes the verification_ratio.
    """
    state = dict(state)
    sub_questions = state.get("sub_questions", [])

    total = 0
    verified_count = 0

    for sq in sub_questions:
        for ev in sq.get("evidence", []):
            total += 1
            # Placeholder verification – mark as verified
            ev["verification_status"] = "verified"
            verified_count += 1

    state["sub_questions"] = sub_questions

    # Compute ratio
    if total > 0:
        state["verification_ratio"] = verified_count / total
    else:
        state["verification_ratio"] = 0.0

    return state


# -- Node 5: synthesize ----------------------------------------------------


def synthesize_node(state: AgentState) -> AgentState:
    """Merge all verified evidence across sub-questions and remove duplicates."""
    state = dict(state)
    sub_questions = state.get("sub_questions", [])

    seen_texts: set[str] = set()
    merged: list[dict] = []

    for sq in sub_questions:
        for ev in sq.get("evidence", []):
            text_key = ev["text"]
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                merged.append(ev)

    state["evidence"] = merged
    return state


# -- Node 6: answer --------------------------------------------------------


def answer_node(state: AgentState) -> AgentState:
    """Generate the final answer with citations.

    Placeholder: composes an answer from the evidence.
    """
    state = dict(state)
    evidence = state.get("evidence", [])
    query = state.get("query", "")

    if state.get("error"):
        state["answer"] = f"An error occurred during research: {state['error']}"
        state["citations"] = []
        return state

    # Build answer text
    parts: list[str] = []
    citations: list[str] = []

    for i, ev in enumerate(evidence):
        parts.append(ev["text"])
        citations.append(f"[{ev.get('source', 'unknown')} - evidence #{i + 1}]")

    state["answer"] = (
        f"Research results for '{query}':\n\n" + "\n".join(parts)
        if parts
        else (f"No evidence found for '{query}'.")
    )
    state["citations"] = citations
    return state


# -- Node 7: log -----------------------------------------------------------


def log_node(state: AgentState) -> AgentState:
    """Log the complete run with all metadata.

    Captures timestamps and aggregates metadata for downstream
    persistence or API responses.
    """
    state = dict(state)
    import datetime

    run_id = str(uuid.uuid4())

    strategies_used = list(
        {
            sq.get("strategy", "unknown")
            for sq in state.get("sub_questions", [])
            if sq.get("strategy")
        }
    )

    state["metadata"] = {
        "run_id": run_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "analysis": state.get("analysis", {}),
        "verification_ratio": state.get("verification_ratio", 0.0),
        "strategies_used": strategies_used,
        "num_sub_questions": len(state.get("sub_questions", [])),
        "num_evidence": len(state.get("evidence", [])),
        "error": state.get("error"),
    }
    logger.info(
        "Research run %s completed. %d evidence items.",
        run_id,
        len(state.get("evidence", [])),
    )
    return state


# -- Node 8: finalize ------------------------------------------------------


def finalize_node(state: AgentState) -> AgentState:
    """Wrap the final Response object and end the graph."""
    # Nothing to add – the caller extracts the Response from state.
    return state


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------


def _route_after_analyze(state: AgentState) -> str:
    """Skip decompose for simple queries; always decompose for others."""
    complexity = state.get("analysis", {}).get("complexity", "moderate")
    if complexity == "simple":
        return "retrieve"
    return "decompose"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def create_research_pipeline(llm: BaseLanguageModel | None = None) -> Any:
    """Build and return the compiled LangGraph StateGraph.

    Args:
        llm: Optional LLM instance for future LLM-based analysis,
             decomposition, and answer generation.  Currently unused
             but wired in for the real implementations.

    Returns:
        The compiled LangGraph ``Graph`` ready to accept ``AgentState``
        inputs.
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("analyze", _safe_node(analyze_node, "analyze"))
    graph.add_node("decompose", _safe_node(decompose_node, "decompose"))
    graph.add_node("retrieve", _safe_node(retrieve_node, "retrieve"))
    graph.add_node("verify", _safe_node(verify_node, "verify"))
    graph.add_node("synthesize", _safe_node(synthesize_node, "synthesize"))
    graph.add_node("answer", _safe_node(answer_node, "answer"))
    graph.add_node("log", _safe_node(log_node, "log"))
    graph.add_node("finalize", _safe_node(finalize_node, "finalize"))

    # Edges
    graph.set_entry_point("analyze")
    graph.add_conditional_edges(
        "analyze",
        _route_after_analyze,
        {"decompose": "decompose", "retrieve": "retrieve"},
    )
    graph.add_edge("decompose", "retrieve")
    graph.add_edge("retrieve", "verify")
    graph.add_edge("verify", "synthesize")
    graph.add_edge("synthesize", "answer")
    graph.add_edge("answer", "log")
    graph.add_edge("log", "finalize")
    graph.add_edge("finalize", END)

    compiled = graph.compile()

    # Expose a convenience method on the compiled graph for building Response
    # (stored as an attribute so the caller can use: graph.run(state))
    def _run(state: dict) -> Response:
        final_state = compiled.invoke(state)
        return Response(
            answer=final_state.get("answer", ""),
            citations=final_state.get("citations", []),
            metadata=final_state.get("metadata", {}),
            error=final_state.get("error"),
        )

    # Type ignores because compiled graph is langgraph's internal type
    compiled.run = _run  # type: ignore[attr-defined]

    return compiled
