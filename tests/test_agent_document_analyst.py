"""Unit tests for Document Analysis Agent (P9-3)."""

from lakenterprises.agents.document_analyst import DocumentAnalysisAgent
from lakenterprises.agents.schemas import DocumentAnalysisResult


def test_document_analyst_agent_standard():
    agent = DocumentAnalysisAgent()
    doc_text = (
        "Enterprise Services Agreement between LakEnterprises and Acme Corp. "
        "Total consideration is $45,000 payable Net-30."
    )
    result = agent.analyze_document(
        document_text=doc_text,
        document_id="DOC-9001",
        doc_type="contract",
        context={"vendor": "Acme Corp", "amount": 45000.0},
    )

    assert isinstance(result, DocumentAnalysisResult)
    assert result.document_id == "DOC-9001"
    assert len(result.key_findings) >= 2
    assert result.extracted_entities["vendor"] == "Acme Corp"
    assert result.confidence >= 0.9


def test_document_analyst_agent_risk_signals():
    agent = DocumentAnalysisAgent()
    result = agent.analyze_document(
        document_text="High risk contract without indemnification",
        document_id="DOC-RISK",
        context={"high_risk": True},
    )

    assert len(result.risk_signals) >= 1
    assert "Missing limitation of liability" in result.risk_signals[0]
