"""Knowledge Retrieval Agent (P9-5)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from lakenterprises.agents.base import BaseSpecialistAgent
from lakenterprises.agents.schemas import AgentRole, AgentTask, KnowledgeRetrievalResult


class KnowledgeRetrievalAgent(BaseSpecialistAgent[KnowledgeRetrievalResult]):
    """Specialist agent querying knowledge bases, memory stores, and tools for grounded facts."""

    role = AgentRole.KNOWLEDGE_RETRIEVER
    output_schema = KnowledgeRetrievalResult

    def retrieve_knowledge(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeRetrievalResult:
        """Search multi-source enterprise knowledge stores and synthesize grounded evidence."""
        task = AgentTask(
            role=self.role,
            instruction=f"Retrieve facts and citations for query: {query}",
            context=context or {},
            parameters={"query": query},
        )
        result = self.run(task)
        if result.status.value == "completed":
            return KnowledgeRetrievalResult.model_validate(result.output_data)
        return KnowledgeRetrievalResult(query=query, facts=[], citations=[])
