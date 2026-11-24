"""Unit tests for Knowledge Retrieval Agent (P9-5)."""

from lakenterprises.agents.knowledge_retriever import KnowledgeRetrievalAgent
from lakenterprises.agents.schemas import KnowledgeRetrievalResult


def test_knowledge_retriever_agent():
    agent = KnowledgeRetrievalAgent()
    res = agent.retrieve_knowledge(
        query="What are the standard hardware procurement guidelines?"
    )

    assert isinstance(res, KnowledgeRetrievalResult)
    assert len(res.facts) >= 2
    assert "KB-PROC-01" in res.citations
    assert res.facts[0].relevance_score >= 0.8
    assert res.coverage_assessment == "complete"
