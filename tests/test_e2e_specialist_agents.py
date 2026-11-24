"""End-to-end multi-agent specialist collaboration test."""

from lakenterprises.agents.compliance import ComplianceAgent
from lakenterprises.agents.document_analyst import DocumentAnalysisAgent
from lakenterprises.agents.escalation_handoff import EscalationHandoffAgent
from lakenterprises.agents.knowledge_retriever import KnowledgeRetrievalAgent
from lakenterprises.agents.response_drafter import ResponseDraftingAgent
from lakenterprises.agents.schemas import AgentRole
from lakenterprises.agents.supervisor import SupervisorAgent


def test_e2e_specialist_agent_collaboration_pipeline():
    """E2E Scenario: A complex enterprise contract review workflow across all 6 specialist agents."""
    # 1. Initialize specialist agents
    supervisor = SupervisorAgent()
    doc_analyst = DocumentAnalysisAgent()
    compliance = ComplianceAgent()
    retriever = KnowledgeRetrievalAgent()
    drafter = ResponseDraftingAgent()
    escalation = EscalationHandoffAgent()

    # Step 1: Supervisor decomposes enterprise goal
    goal = "Evaluate vendor agreement for Acme Corp and prepare contract response."
    plan = supervisor.plan_workflow(goal)
    assert plan.next_agent == AgentRole.DOCUMENT_ANALYST

    # Step 2: Document Analyst parses contract terms
    doc_text = "Master Agreement with Acme Corp for $45,000 cloud infrastructure."
    analysis = doc_analyst.analyze_document(
        doc_text,
        document_id="DOC-ACME-01",
        context={"vendor": "Acme Corp", "amount": 45000.0},
    )
    assert analysis.extracted_entities["vendor"] == "Acme Corp"

    # Step 3: Compliance Agent validates transaction limit
    comp = compliance.check_compliance(
        policy_name="Global Procurement Policy",
        transaction_details={
            "amount": analysis.extracted_entities["amount"],
            "vendor": analysis.extracted_entities["vendor"],
        },
    )
    assert comp.is_compliant is True

    # Step 4: Knowledge Retriever finds SLA citations
    knowledge = retriever.retrieve_knowledge("Acme Corp SLA and discount terms")
    assert len(knowledge.citations) >= 1

    # Step 5: Response Drafter writes approval memo with citation
    draft = drafter.draft_response(
        purpose="Confirm contract terms",
        facts=[f.snippet for f in knowledge.facts],
        recipient="Acme Procurement",
    )
    assert "Dear Partner" in draft.draft_text
    assert len(draft.citations) >= 1

    # Step 6: Escalation Agent verifies no critical threats exist
    esc = escalation.evaluate_escalation(
        incident_description="Standard contract review complete.",
        severity_hint="LOW",
    )
    assert esc.requires_human is False
