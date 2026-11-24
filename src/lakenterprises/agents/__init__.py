"""Phase 9 Specialist Agents for the LakEnterprises Platform.

Includes schemas, deterministic offline FakeLLMHarness, BaseSpecialistAgent,
and the 6 domain specialist agents along with evaluation datasets.
"""

from lakenterprises.agents.base import BaseSpecialistAgent
from lakenterprises.agents.compliance import ComplianceAgent
from lakenterprises.agents.document_analyst import DocumentAnalysisAgent
from lakenterprises.agents.escalation_handoff import EscalationHandoffAgent
from lakenterprises.agents.eval_dataset import (
    BENCHMARK_SCENARIOS,
    EvalScenario,
    evaluate_scenario,
)
from lakenterprises.agents.fake_llm import FakeLLMHarness, default_fake_llm
from lakenterprises.agents.knowledge_retriever import KnowledgeRetrievalAgent
from lakenterprises.agents.response_drafter import ResponseDraftingAgent
from lakenterprises.agents.schemas import (
    AgentResult,
    AgentRole,
    AgentTask,
    AgentTaskStatus,
    ComplianceResult,
    ComplianceViolation,
    DocumentAnalysisResult,
    EscalationHandoffResult,
    KnowledgeRetrievalResult,
    ResponseDraftResult,
    RetrievedFact,
    SupervisorPlan,
)
from lakenterprises.agents.supervisor import SupervisorAgent

__all__ = [
    # Base and Harness
    "BaseSpecialistAgent",
    "FakeLLMHarness",
    "default_fake_llm",
    # Agents
    "SupervisorAgent",
    "DocumentAnalysisAgent",
    "ComplianceAgent",
    "KnowledgeRetrievalAgent",
    "ResponseDraftingAgent",
    "EscalationHandoffAgent",
    # Schemas
    "AgentRole",
    "AgentTaskStatus",
    "AgentTask",
    "AgentResult",
    "SupervisorPlan",
    "DocumentAnalysisResult",
    "ComplianceViolation",
    "ComplianceResult",
    "RetrievedFact",
    "KnowledgeRetrievalResult",
    "ResponseDraftResult",
    "EscalationHandoffResult",
    # Evaluation
    "EvalScenario",
    "BENCHMARK_SCENARIOS",
    "evaluate_scenario",
]
