"""Unit tests for Response Drafting Agent (P9-6)."""

from lakenterprises.agents.response_drafter import ResponseDraftingAgent
from lakenterprises.agents.schemas import ResponseDraftResult


def test_response_drafter_agent():
    agent = ResponseDraftingAgent()
    res = agent.draft_response(
        purpose="Notify partner of approved proposal",
        recipient="Acme Partner",
        tone="professional",
    )

    assert isinstance(res, ResponseDraftResult)
    assert res.recipient == "Acme Partner"
    assert res.tone == "professional"
    assert len(res.citations) >= 1
    assert "Dear Partner" in res.draft_text
    assert len(res.key_points) >= 2
