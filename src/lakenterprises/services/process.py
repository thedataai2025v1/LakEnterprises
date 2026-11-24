"""Process orchestration service for templates, instances, tasks, and state machine transitions."""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from lakenterprises.models.entities import (ProcessInstance, ProcessTask,
                                            ProcessTemplate)
from lakenterprises.models.enums import ProcessStatus, TaskStatus
from lakenterprises.repositories import (ProcessInstanceRepository,
                                         ProcessTaskRepository,
                                         ProcessTemplateRepository)

logger = logging.getLogger(__name__)


# ── Allowed State Machine Transitions ─────────────────────────────────────────

VALID_INSTANCE_TRANSITIONS: dict[str, set[str]] = {
    ProcessStatus.PENDING.value: {
        ProcessStatus.ACTIVE.value,
        ProcessStatus.CANCELLED.value,
    },
    ProcessStatus.ACTIVE.value: {
        ProcessStatus.PAUSED.value,
        ProcessStatus.COMPLETED.value,
        ProcessStatus.FAILED.value,
        ProcessStatus.CANCELLED.value,
    },
    ProcessStatus.PAUSED.value: {
        ProcessStatus.ACTIVE.value,
        ProcessStatus.CANCELLED.value,
    },
    # Terminal states: no outbound transitions
    ProcessStatus.COMPLETED.value: set(),
    ProcessStatus.FAILED.value: set(),
    ProcessStatus.CANCELLED.value: set(),
}

VALID_TASK_TRANSITIONS: dict[str, set[str]] = {
    TaskStatus.PENDING.value: {
        TaskStatus.IN_PROGRESS.value,
        TaskStatus.COMPLETED.value,
        TaskStatus.SKIPPED.value,
        TaskStatus.FAILED.value,
    },
    TaskStatus.IN_PROGRESS.value: {
        TaskStatus.COMPLETED.value,
        TaskStatus.FAILED.value,
    },
    # Terminal states
    TaskStatus.COMPLETED.value: set(),
    TaskStatus.FAILED.value: set(),
    TaskStatus.SKIPPED.value: set(),
}


class ProcessService:
    """Service encapsulating business logic for enterprise processes."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.template_repo = ProcessTemplateRepository(db)
        self.instance_repo = ProcessInstanceRepository(db)
        self.task_repo = ProcessTaskRepository(db)

    # ── Template Operations ───────────────────────────────────────────────────

    def create_template(
        self,
        name: str,
        description: Optional[str] = None,
        version: int = 1,
        definition: Optional[dict[str, Any]] = None,
        is_active: bool = True,
    ) -> ProcessTemplate:
        """Create a new process blueprint template."""
        definition = definition or {}
        # Ensure definition has 'steps' list structure if provided
        if "steps" not in definition:
            definition["steps"] = []
        tpl = self.template_repo.create(
            name=name,
            description=description,
            version=version,
            definition=definition,
            is_active=is_active,
        )
        self.db.commit()
        return tpl

    def get_template(self, template_id: str) -> Optional[ProcessTemplate]:
        return self.template_repo.get_by_id(template_id)

    def get_template_by_name(self, name: str) -> Optional[ProcessTemplate]:
        return self.template_repo.get_by_name(name)

    def list_templates(self, active_only: bool = False) -> list[ProcessTemplate]:
        return self.template_repo.get_all(active_only=active_only)

    def update_template(
        self,
        template_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        version: Optional[int] = None,
        definition: Optional[dict[str, Any]] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[ProcessTemplate]:
        return self.template_repo.update(
            template_id,
            name=name,
            description=description,
            version=version,
            definition=definition,
            is_active=is_active,
        )

    def delete_template(self, template_id: str) -> bool:
        res = self.template_repo.delete(template_id)
        if res:
            self.db.commit()
        return res

    # ── Instance Operations ───────────────────────────────────────────────────

    def start_process(
        self,
        template_id: str,
        title: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        created_by_id: Optional[str] = None,
    ) -> ProcessInstance:
        """Instantiate a process template and materialize its tasks."""
        template = self.template_repo.get_by_id(template_id)
        if not template:
            raise ValueError(f"Process template '{template_id}' not found")
        if not template.is_active:
            raise ValueError(f"Process template '{template.name}' is inactive")

        instance_title = title or f"{template.name} - Instance"
        instance = self.instance_repo.create(
            template_id=template.id,
            title=instance_title,
            status=ProcessStatus.ACTIVE.value,
            context=context or {},
            created_by_id=created_by_id,
        )

        # Materialize tasks from template definition
        steps = template.definition.get("steps", []) if template.definition else []
        for idx, step in enumerate(steps):
            step_name = step.get("name", f"Step {idx + 1}")
            step_desc = step.get("description", "")
            assignee_role = step.get("role")
            self.task_repo.create(
                instance_id=instance.id,
                position=idx,
                name=step_name,
                description=step_desc,
                assignee_role=assignee_role,
                status=TaskStatus.PENDING.value,
            )

        self.db.commit()
        return instance

    def get_instance(self, instance_id: str) -> Optional[ProcessInstance]:
        return self.instance_repo.get_by_id(instance_id)

    def list_instances(
        self,
        status: Optional[str] = None,
        template_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProcessInstance]:
        return self.instance_repo.get_all(
            status=status, template_id=template_id, limit=limit, offset=offset
        )

    def transition_instance(
        self,
        instance_id: str,
        target_status: str,
        context_update: Optional[dict[str, Any]] = None,
    ) -> ProcessInstance:
        """Validate and apply a strict state machine transition for an instance."""
        instance = self.instance_repo.get_by_id(instance_id)
        if not instance:
            raise ValueError(f"Process instance '{instance_id}' not found")

        current_status = instance.status
        allowed = VALID_INSTANCE_TRANSITIONS.get(current_status, set())

        if target_status not in allowed:
            raise ValueError(
                f"Illegal transition from '{current_status}' to '{target_status}'. "
                f"Valid transitions: {sorted(list(allowed))}"
            )

        updated = self.instance_repo.update_status(instance_id, target_status)
        if context_update:
            self.instance_repo.update_context(instance_id, context_update)
        self.db.commit()
        return updated  # type: ignore[return-value]

    # ── Task Operations ───────────────────────────────────────────────────────

    def get_instance_tasks(self, instance_id: str) -> list[ProcessTask]:
        return self.task_repo.get_by_instance_id(instance_id)

    def get_task(self, task_id: str) -> Optional[ProcessTask]:
        return self.task_repo.get_by_id(task_id)

    def update_task_status(
        self,
        task_id: str,
        target_status: str,
        result: Optional[dict[str, Any]] = None,
    ) -> ProcessTask:
        """Update a task's state respecting the task transition rules."""
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found")

        current = task.status
        allowed = VALID_TASK_TRANSITIONS.get(current, set())
        if target_status not in allowed:
            raise ValueError(
                f"Illegal task transition from '{current}' to '{target_status}'. "
                f"Valid transitions: {sorted(list(allowed))}"
            )

        updated = self.task_repo.update_status(task_id, target_status, result)
        self.db.commit()
        return updated  # type: ignore[return-value]
