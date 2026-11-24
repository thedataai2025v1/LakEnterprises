"""Supervisor / Orchestrator Agent (P9-2)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from lakenterprises.agents.base import BaseSpecialistAgent
from lakenterprises.agents.schemas import AgentRole, AgentTask, SupervisorPlan


class SupervisorAgent(BaseSpecialistAgent[SupervisorPlan]):
    """Supervisor agent coordinating workflows, subtask decomposition, and specialist routing."""

    role = AgentRole.SUPERVISOR
    output_schema = SupervisorPlan

    def plan_workflow(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> SupervisorPlan:
        """Analyze a high-level goal and generate a sequence of specialist agent subtasks."""
        task = AgentTask(
            role=self.role,
            instruction=f"Decompose and plan workflow for goal: {goal}",
            context=context or {},
            parameters={"goal": goal},
        )
        result = self.run(task)
        if result.status.value == "completed":
            return SupervisorPlan.model_validate(result.output_data)
        return SupervisorPlan(goal=goal, is_complete=False)
