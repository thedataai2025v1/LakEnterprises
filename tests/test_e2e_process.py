"""End-to-End lifecycle test for Enterprise Process orchestration and CLI."""

import pytest

from lakenterprises.__main__ import main
from lakenterprises.db import get_db_session, reset_db
from lakenterprises.models.entities import Role, User
from lakenterprises.models.enums import ApprovalStatus, ProcessStatus, TaskStatus
from lakenterprises.services.approval import ApprovalService
from lakenterprises.services.process import ProcessService


@pytest.fixture(autouse=True)
def setup_database():
    reset_db()
    with get_db_session() as session:
        admin_role = Role(id="role-admin", name="admin", description="Admin")
        session.add(admin_role)
        session.flush()

        u_admin = User(
            id="admin-system-user",
            username="admin",
            email="admin@lak.com",
            password_hash="fake",
            is_active=True,
            roles=[admin_role],
        )
        session.add(u_admin)
        session.commit()
    yield
    reset_db()


def test_full_process_lifecycle_e2e():
    """Verify complete enterprise workflow from blueprint definition to sign-off."""
    with get_db_session() as session:
        proc_service = ProcessService(session)
        appr_service = ApprovalService(session)

        # 1. Author Process Blueprint Template
        template = proc_service.create_template(
            name="Quarterly Financial Audit Workflow",
            description="End-to-end financial audit and executive clearance pipeline.",
            version=1,
            definition={
                "steps": [
                    {"name": "Ingest Transaction Ledger", "role": "analyst"},
                    {"name": "Run Discrepancy Checks", "role": "analyst"},
                    {"name": "CFO Sign-Off Gate", "role": "manager"},
                    {"name": "File Compliance Certification", "role": "admin"},
                ]
            },
        )
        assert template.id is not None
        assert len(template.definition["steps"]) == 4

        # 2. Instantiate Process for Q4
        instance = proc_service.start_process(
            template_id=template.id,
            title="FY2026 Q4 Financial Audit",
            context={"quarter": "Q4", "year": 2026},
            created_by_id="admin-system-user",
        )
        assert instance.status == ProcessStatus.ACTIVE.value
        tasks = proc_service.get_instance_tasks(instance.id)
        assert len(tasks) == 4

        # 3. Execute Step 1: Ingest Ledger
        proc_service.update_task_status(tasks[0].id, TaskStatus.IN_PROGRESS.value)
        proc_service.update_task_status(
            tasks[0].id,
            TaskStatus.COMPLETED.value,
            result={"entries_loaded": 154200, "status": "clean"},
        )

        # 4. Execute Step 2: Run Discrepancy Checks
        proc_service.update_task_status(tasks[1].id, TaskStatus.IN_PROGRESS.value)
        proc_service.update_task_status(
            tasks[1].id,
            TaskStatus.COMPLETED.value,
            result={"variance": 0.0, "flagged_anomalies": 0},
        )

        # 5. Pause instance during audit review
        paused_inst = proc_service.transition_instance(
            instance.id, ProcessStatus.PAUSED.value
        )
        assert paused_inst.status == ProcessStatus.PAUSED.value

        # 6. Resume instance
        resumed_inst = proc_service.transition_instance(
            instance.id, ProcessStatus.ACTIVE.value
        )
        assert resumed_inst.status == ProcessStatus.ACTIVE.value

        # 7. Step 3: Trigger Approval Gate for CFO Sign-off
        approval = appr_service.request_approval(
            target_type="process_instance",
            target_id=instance.id,
            action="cfo_signoff",
            requested_by_id="admin-system-user",
        )
        assert approval.status == ApprovalStatus.PENDING.value

        # CFO grants approval
        reviewed = appr_service.approve(
            request_id=approval.id,
            reviewed_by_id="cfo-user-id",
            comment="All variance checks verified clean. Ready to file.",
        )
        assert reviewed.status == ApprovalStatus.APPROVED.value
        proc_service.update_task_status(
            tasks[2].id,
            TaskStatus.COMPLETED.value,
            result={"approval_id": reviewed.id, "approved_by": "cfo-user-id"},
        )

        # 8. Step 4: Final Certification
        proc_service.update_task_status(tasks[3].id, TaskStatus.IN_PROGRESS.value)
        proc_service.update_task_status(
            tasks[3].id,
            TaskStatus.COMPLETED.value,
            result={"certification_hash": "sha256-a94f82c..."},
        )

        # 9. Complete Process
        completed_inst = proc_service.transition_instance(
            instance.id,
            ProcessStatus.COMPLETED.value,
            context_update={"filed_at": "2026-11-24T12:00:00Z"},
        )
        assert completed_inst.status == ProcessStatus.COMPLETED.value
        assert completed_inst.context["filed_at"] == "2026-11-24T12:00:00Z"


def test_cli_process_run_demo(capsys):
    """Test running process CLI demo command."""
    main(["process", "run-demo"])
    captured = capsys.readouterr()
    assert "Running Canonical Enterprise Process Demo" in captured.out
    assert (
        "Process Lifecycle Finished! Final Instance Status: COMPLETED" in captured.out
    )
