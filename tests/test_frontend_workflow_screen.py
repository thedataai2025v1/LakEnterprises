"""Tests for Phase 13 Process workflow screen components and workflow routes integration."""

import os

from fastapi.testclient import TestClient

from lakenterprises.app import create_app
from lakenterprises.ui import get_frontend_dir


class TestProcessWorkflowScreenIntegration:
    """Validate Phase 13 process workflow screen components and API contracts."""

    def test_frontend_workflow_components_exist(self):
        """Ensure all required workflow UI components and pages are present."""
        fe_dir = get_frontend_dir()
        src_dir = os.path.join(fe_dir, "src")

        # Process detail page
        detail_page = os.path.join(src_dir, "app", "processes", "[id]", "page.tsx")
        assert os.path.isfile(detail_page)

        # Workflow components
        timeline_comp = os.path.join(
            src_dir, "components", "workflow", "process-timeline.tsx"
        )
        assert os.path.isfile(timeline_comp)

        steps_comp = os.path.join(
            src_dir, "components", "workflow", "workflow-steps-panel.tsx"
        )
        assert os.path.isfile(steps_comp)

        actions_comp = os.path.join(
            src_dir, "components", "workflow", "process-actions.tsx"
        )
        assert os.path.isfile(actions_comp)

    def test_workflow_api_flow_for_frontend_screen(self):
        """Verify the complete workflow state, events, and decide cycle for the frontend screen."""
        app = create_app()
        client = TestClient(app)

        # 1. Obtain demo analyst token
        auth_res = client.post("/api/v1/auth/demo/analyst")
        assert auth_res.status_code == 200
        token = auth_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Run a workflow that pauses at human approval ($150,000 dispute)
        payload = {
            "title": "Vendor Invoice Dispute $150k",
            "instruction": "Audit high value invoice #INV-9021 for Acme Corp",
            "input_payload": {"amount": 150000.0, "severity": "CRITICAL"},
        }
        run_res = client.post(
            "/api/v1/workflow/run",
            headers=headers,
            json=payload,
        )
        assert run_res.status_code == 200
        state = run_res.json()
        process_id = state["process_id"]
        assert state.get("approval_required") is True
        assert state.get("current_status") in [
            "AWAITING_APPROVAL",
            "pending",
            "in_progress",
        ]

        # 3. Frontend queries workflow state
        state_res = client.get(f"/api/v1/workflow/{process_id}/state", headers=headers)
        assert state_res.status_code == 200
        state_data = state_res.json()
        assert state_data["process_id"] == process_id

        # 4. Frontend queries workflow events stream
        events_res = client.get(
            f"/api/v1/workflow/{process_id}/events", headers=headers
        )
        assert events_res.status_code == 200
        events = events_res.json()
        assert isinstance(events, list)

        # 5. Frontend queries SLA metrics
        sla_res = client.get(f"/api/v1/workflow/{process_id}/sla", headers=headers)
        assert sla_res.status_code == 200
        sla_data = sla_res.json()
        assert "tier" in sla_data
        assert "sla_hours" in sla_data

        # 6. Frontend operator submits decision: APPROVED
        decide_res = client.post(
            f"/api/v1/workflow/{process_id}/decide",
            headers=headers,
            json={
                "decision": "APPROVED",
                "notes": "Verified by Senior Finance Analyst via UI screen",
            },
        )
        assert decide_res.status_code == 200
        resumed_state = decide_res.json()
        assert resumed_state.get("approval_status") == "approved"
