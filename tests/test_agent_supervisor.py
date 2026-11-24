"""Unit tests for Supervisor / Orchestrator Agent (P9-2)."""

from lakenterprises.agents.fake_llm import FakeLLMHarness
from lakenterprises.agents.schemas import AgentRole, SupervisorPlan
from lakenterprises.agents.supervisor import SupervisorAgent


def test_supervisor_agent_plan_workflow():
    agent = SupervisorAgent()
    plan = agent.plan_workflow(
        goal="Audit and approve enterprise procurement request for Acme",
        context={"customer": "Acme Global", "amount": 45000.0},
    )

    assert isinstance(plan, SupervisorPlan)
    assert plan.next_agent == AgentRole.DOCUMENT_ANALYST
    assert len(plan.planned_agents) >= 3
    assert len(plan.subtasks) >= 3
    assert plan.is_complete is False


def test_supervisor_agent_custom_plan():
    harness = FakeLLMHarness()
    harness.register_response(
        "emergency",
        {
            "goal": "Emergency patch",
            "next_agent": "escalation_handoff",
            "planned_agents": ["escalation_handoff"],
            "subtasks": [
                {"step": 1, "agent": "escalation_handoff", "task": "Page on-call"}
            ],
            "is_complete": False,
            "final_summary": None,
        },
    )
    agent = SupervisorAgent(llm_harness=harness)
    plan = agent.plan_workflow("Emergency security response")
    assert plan.next_agent == AgentRole.ESCALATION_HANDOFF
    assert plan.subtasks[0]["task"] == "Page on-call"
