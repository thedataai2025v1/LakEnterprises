"""Unit and integration tests for ProcessService and state machine transitions."""

import pytest

from lakenterprises.db import get_db_session, reset_db
from lakenterprises.models.enums import ProcessStatus, TaskStatus
from lakenterprises.services.process import ProcessService


@pytest.fixture(autouse=True)
def setup_database():
    reset_db()
    yield
    reset_db()


def test_template_crud():
    with get_db_session() as session:
        service = ProcessService(session)

        # Create
        tpl = service.create_template(
            name="Incident Review Workflow",
            description="Review incidents quarterly",
            version=1,
            definition={
                "steps": [
                    {"name": "Extract Records", "role": "analyst"},
                    {"name": "Sign-off", "role": "manager"},
                ]
            },
        )
        assert tpl.id is not None
        assert tpl.name == "Incident Review Workflow"

        # Read
        fetched = service.get_template(tpl.id)
        assert fetched is not None
        assert fetched.name == "Incident Review Workflow"

        by_name = service.get_template_by_name("Incident Review Workflow")
        assert by_name is not None
        assert by_name.id == tpl.id

        templates = service.list_templates()
        assert len(templates) >= 1

        # Update
        updated = service.update_template(
            tpl.id, name="Updated Workflow", description="Updated description"
        )
        assert updated.name == "Updated Workflow"
        assert updated.description == "Updated description"

        # Delete
        assert service.delete_template(tpl.id) is True
        assert service.get_template(tpl.id) is None


def test_process_lifecycle_and_state_machine():
    with get_db_session() as session:
        service = ProcessService(session)

        # Create template with 2 steps
        tpl = service.create_template(
            name="Lifecycle Template",
            definition={
                "steps": [
                    {"name": "Task 1", "role": "analyst"},
                    {"name": "Task 2", "role": "admin"},
                ]
            },
        )

        # Start instance
        inst = service.start_process(
            template_id=tpl.id,
            title="Production Lifecycle Run",
            context={"env": "prod"},
        )
        assert inst.status == ProcessStatus.ACTIVE.value
        assert inst.title == "Production Lifecycle Run"

        # Verify materialized tasks
        tasks = service.get_instance_tasks(inst.id)
        assert len(tasks) == 2
        assert tasks[0].name == "Task 1"
        assert tasks[0].status == TaskStatus.PENDING.value
        assert tasks[1].name == "Task 2"

        # Progress Task 1: pending -> in_progress -> completed
        t1 = service.update_task_status(tasks[0].id, TaskStatus.IN_PROGRESS.value)
        assert t1.status == "in_progress"

        t1_done = service.update_task_status(
            tasks[0].id, TaskStatus.COMPLETED.value, result={"items": 10}
        )
        assert t1_done.status == "completed"
        assert t1_done.result["items"] == 10

        # Illegal Task transition: completed -> in_progress should raise ValueError
        with pytest.raises(ValueError, match="Illegal task transition"):
            service.update_task_status(tasks[0].id, TaskStatus.IN_PROGRESS.value)

        # Instance State transitions: active -> paused -> active -> completed
        p_paused = service.transition_instance(inst.id, ProcessStatus.PAUSED.value)
        assert p_paused.status == "paused"

        p_resumed = service.transition_instance(inst.id, ProcessStatus.ACTIVE.value)
        assert p_resumed.status == "active"

        p_completed = service.transition_instance(
            inst.id, ProcessStatus.COMPLETED.value, context_update={"finished": True}
        )
        assert p_completed.status == "completed"
        assert p_completed.context["finished"] is True

        # Illegal Instance transition: completed -> active should raise ValueError
        with pytest.raises(ValueError, match="Illegal transition"):
            service.transition_instance(inst.id, ProcessStatus.ACTIVE.value)


def test_start_process_invalid_template():
    with get_db_session() as session:
        service = ProcessService(session)
        with pytest.raises(ValueError, match="not found"):
            service.start_process("non-existent-template-id")


def test_inactive_template_instantiation():
    with get_db_session() as session:
        service = ProcessService(session)
        tpl = service.create_template(name="Inactive Template", is_active=False)
        with pytest.raises(ValueError, match="is inactive"):
            service.start_process(tpl.id)
