"""Benchmark evaluation dataset tests (P9-8)."""

from lakenterprises.agents.compliance import ComplianceAgent
from lakenterprises.agents.document_analyst import DocumentAnalysisAgent
from lakenterprises.agents.escalation_handoff import EscalationHandoffAgent
from lakenterprises.agents.eval_dataset import (
    BENCHMARK_SCENARIOS,
    evaluate_scenario,
)
from lakenterprises.agents.knowledge_retriever import KnowledgeRetrievalAgent
from lakenterprises.agents.response_drafter import ResponseDraftingAgent
from lakenterprises.agents.schemas import AgentRole
from lakenterprises.agents.supervisor import SupervisorAgent


def test_benchmark_scenarios_all_pass():
    agents_map = {
        AgentRole.SUPERVISOR: SupervisorAgent(),
        AgentRole.DOCUMENT_ANALYST: DocumentAnalysisAgent(),
        AgentRole.COMPLIANCE: ComplianceAgent(),
        AgentRole.KNOWLEDGE_RETRIEVER: KnowledgeRetrievalAgent(),
        AgentRole.RESPONSE_DRAFTER: ResponseDraftingAgent(),
        AgentRole.ESCALATION_HANDOFF: EscalationHandoffAgent(),
    }

    assert len(BENCHMARK_SCENARIOS) >= 6

    for scenario in BENCHMARK_SCENARIOS:
        agent = agents_map[scenario.target_role]
        result = evaluate_scenario(agent, scenario)
        assert (
            result["passed"] is True
        ), f"Failed on {scenario.id}: {result.get('failures')}"
        assert result["confidence"] >= 0.8
