"""Document Analysis Agent (P9-3)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from lakenterprises.agents.base import BaseSpecialistAgent
from lakenterprises.agents.schemas import AgentRole, AgentTask, DocumentAnalysisResult


class DocumentAnalysisAgent(BaseSpecialistAgent[DocumentAnalysisResult]):
    """Specialist agent analyzing text documents, extracting entities, and detecting risky clauses."""

    role = AgentRole.DOCUMENT_ANALYST
    output_schema = DocumentAnalysisResult

    def analyze_document(
        self,
        document_text: str,
        document_id: Optional[str] = None,
        doc_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> DocumentAnalysisResult:
        """Perform deep structured analysis of a contract, invoice, or technical document."""
        task = AgentTask(
            role=self.role,
            instruction=f"Analyze document: {document_text[:200]}...",
            context=context or {},
            parameters={
                "document_text": document_text,
                "document_id": document_id or "DOC-AUTO",
                "doc_type": doc_type or "contract",
            },
        )
        result = self.run(task)
        if result.status.value == "completed":
            return DocumentAnalysisResult.model_validate(result.output_data)
        return DocumentAnalysisResult(
            document_id=document_id,
            key_findings=["Failed to analyze document."],
            confidence=0.0,
        )
