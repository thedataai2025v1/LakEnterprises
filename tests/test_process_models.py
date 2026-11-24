"""Unit tests for Phase 5 database models and enums."""

import pytest

from lakenterprises.models.entities import (ApprovalRequest, ProcessInstance,
                                            ProcessTask, ProcessTemplate)
from lakenterprises.models.enums import (ApprovalStatus, ProcessStatus,
                                         TaskStatus)


def test_process_enums():
    assert ProcessStatus.PENDING == "pending"
    assert ProcessStatus.ACTIVE == "active"
    assert ProcessStatus.PAUSED == "paused"
    assert ProcessStatus.COMPLETED == "completed"
    assert ProcessStatus.FAILED == "failed"
    assert ProcessStatus.CANCELLED == "cancelled"

    assert TaskStatus.PENDING == "pending"
    assert TaskStatus.IN_PROGRESS == "in_progress"
    assert TaskStatus.COMPLETED == "completed"
    assert TaskStatus.FAILED == "failed"
    assert TaskStatus.SKIPPED == "skipped"

    assert ApprovalStatus.PENDING == "pending"
    assert ApprovalStatus.APPROVED == "approved"
    assert ApprovalStatus.REJECTED == "rejected"


def test_process_template_model():
    tpl = ProcessTemplate(
        id="tpl-123",
        name="Test Workflow",
        description="A test workflow description",
        version=1,
        definition={"steps": [{"name": "Step 1"}]},
        is_active=True,
    )
    assert tpl.id == "tpl-123"
    assert tpl.name == "Test Workflow"
    assert tpl.version == 1
    assert "tpl-123" in repr(tpl)


def test_process_instance_model():
    inst = ProcessInstance(
        id="inst-123",
        template_id="tpl-123",
        title="Q3 Review",
        status=ProcessStatus.ACTIVE.value,
        context={"quarter": "Q3"},
    )
    assert inst.id == "inst-123"
    assert inst.status == "active"
    assert inst.context["quarter"] == "Q3"
    assert "inst-123" in repr(inst)


def test_process_task_model():
    task = ProcessTask(
        id="task-123",
        instance_id="inst-123",
        position=0,
        name="Extract Incidents",
        status=TaskStatus.PENDING.value,
        result={"count": 5},
    )
    assert task.id == "task-123"
    assert task.position == 0
    assert task.status == "pending"
    assert "task-123" in repr(task)


def test_approval_request_model():
    req = ApprovalRequest(
        id="appr-123",
        target_type="process_instance",
        target_id="inst-123",
        action="executive_signoff",
        requested_by_id="user-1",
        status=ApprovalStatus.PENDING.value,
    )
    assert req.id == "appr-123"
    assert req.action == "executive_signoff"
    assert req.status == "pending"
    assert "appr-123" in repr(req)
