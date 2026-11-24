"""Base abstraction for Phase 9 specialist agents."""

from __future__ import annotations

import logging
import time
from typing import Generic, Optional, Type, TypeVar

from pydantic import BaseModel

from lakenterprises.agents.fake_llm import FakeLLMHarness, default_fake_llm
from lakenterprises.agents.schemas import (
    AgentResult,
    AgentRole,
    AgentTask,
    AgentTaskStatus,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseSpecialistAgent(Generic[T]):
    """Abstract base class for all specialist enterprise agents."""

    role: AgentRole
    output_schema: Type[T]

    def __init__(
        self,
        name: Optional[str] = None,
        llm_harness: Optional[FakeLLMHarness] = None,
    ) -> None:
        self.name = name or self.__class__.__name__
        self.llm = llm_harness or default_fake_llm

    def build_prompt(self, task: AgentTask) -> str:
        """Construct the prompt string sent to the underlying language model."""
        parts = [
            f"=== ROLE: {self.role.value.upper()} ===",
            f"INSTRUCTION: {task.instruction}",
        ]
        if task.context:
            parts.append(f"CONTEXT: {task.context}")
        if task.parameters:
            parts.append(f"PARAMETERS: {task.parameters}")
        return "\n".join(parts)

    def run(self, task: AgentTask) -> AgentResult:
        """Execute the agent task and return a validated AgentResult."""
        start_time = time.perf_counter()
        prompt = self.build_prompt(task)

        try:
            raw_output = self.llm.generate(
                role=self.role,
                prompt=prompt,
                context={**task.context, **task.parameters},
            )

            # Validate output against the specialist's target Pydantic schema
            parsed_data = self.output_schema.model_validate(raw_output)
            output_dict = parsed_data.model_dump()

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Extract citations if present in output schema
            citations = getattr(parsed_data, "citations", []) or []

            return AgentResult(
                task_id=task.task_id,
                role=self.role,
                status=AgentTaskStatus.COMPLETED,
                output_data=output_dict,
                reasoning=f"{self.name} completed successfully.",
                citations=citations,
                confidence_score=getattr(parsed_data, "confidence", 1.0) or 1.0,
                metrics={
                    "latency_ms": round(latency_ms, 2),
                    "model": "fake-llm-harness",
                    "role": self.role.value,
                },
            )

        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error("Agent %s failed on task %s: %s", self.name, task.task_id, exc)
            return AgentResult(
                task_id=task.task_id,
                role=self.role,
                status=AgentTaskStatus.FAILED,
                output_data={},
                reasoning=f"Execution error: {exc}",
                error=str(exc),
                confidence_score=0.0,
                metrics={"latency_ms": round(latency_ms, 2)},
            )
