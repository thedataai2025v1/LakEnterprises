"""FastAPI endpoints for Process Templates, Instances, Tasks, and Approvals.

RBAC:
- View templates/instances/tasks: viewer, analyst, admin
- Create/update/delete templates: analyst, admin
- Start instance / transition instance: analyst, admin
- Update task: analyst, admin
- Request approval: viewer, analyst, admin
- Approve/Reject approval: manager, admin
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from lakenterprises.auth.middleware import get_current_user, require_role
from lakenterprises.db import get_db_session
from lakenterprises.services.approval import ApprovalService
from lakenterprises.services.process import ProcessService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/processes", tags=["processes"])
approvals_router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    version: int = Field(1, ge=1)
    definition: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[int] = None
    definition: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    version: int
    definition: dict[str, Any]
    is_active: bool
    created_at: str


class InstanceStartRequest(BaseModel):
    template_id: str
    title: Optional[str] = None
    context: Optional[dict[str, Any]] = Field(default_factory=dict)


class InstanceTransitionRequest(BaseModel):
    status: str
    context: Optional[dict[str, Any]] = None


class TaskUpdateRequest(BaseModel):
    status: str
    result: Optional[dict[str, Any]] = None


class TaskResponse(BaseModel):
    id: str
    instance_id: str
    position: int
    name: str
    description: Optional[str]
    assignee_id: Optional[str]
    assignee_role: Optional[str]
    status: str
    result: Optional[dict[str, Any]]
    created_at: str


class InstanceResponse(BaseModel):
    id: str
    template_id: str
    title: str
    status: str
    context: Optional[dict[str, Any]]
    created_by_id: Optional[str]
    created_at: str
    tasks: Optional[list[TaskResponse]] = None


class ApprovalCreateRequest(BaseModel):
    target_type: str
    target_id: str
    action: str


class ApprovalDecisionRequest(BaseModel):
    comment: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: str
    target_type: str
    target_id: str
    action: str
    requested_by_id: str
    status: str
    reviewed_by_id: Optional[str]
    comment: Optional[str]
    created_at: str


# ---------------------------------------------------------------------------
# Process Template Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/templates",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("analyst", "admin"))],
)
def create_template(
    payload: TemplateCreateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with get_db_session() as session:
        service = ProcessService(session)
        existing = service.get_template_by_name(payload.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Template with name '{payload.name}' already exists",
            )
        tpl = service.create_template(
            name=payload.name,
            description=payload.description,
            version=payload.version,
            definition=payload.definition,
            is_active=payload.is_active,
        )
        return {
            "id": tpl.id,
            "name": tpl.name,
            "description": tpl.description,
            "version": tpl.version,
            "definition": tpl.definition,
            "is_active": tpl.is_active,
            "created_at": tpl.created_at.isoformat() if tpl.created_at else "",
        }


@router.get(
    "/templates",
    response_model=list[TemplateResponse],
    dependencies=[Depends(require_role("viewer", "analyst", "admin"))],
)
def list_templates(
    active_only: bool = Query(False),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    with get_db_session() as session:
        service = ProcessService(session)
        templates = service.list_templates(active_only=active_only)
        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "version": t.version,
                "definition": t.definition,
                "is_active": t.is_active,
                "created_at": t.created_at.isoformat() if t.created_at else "",
            }
            for t in templates
        ]


@router.get(
    "/templates/{template_id}",
    response_model=TemplateResponse,
    dependencies=[Depends(require_role("viewer", "analyst", "admin"))],
)
def get_template(
    template_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with get_db_session() as session:
        service = ProcessService(session)
        tpl = service.get_template(template_id)
        if not tpl:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_id}' not found",
            )
        return {
            "id": tpl.id,
            "name": tpl.name,
            "description": tpl.description,
            "version": tpl.version,
            "definition": tpl.definition,
            "is_active": tpl.is_active,
            "created_at": tpl.created_at.isoformat() if tpl.created_at else "",
        }


@router.put(
    "/templates/{template_id}",
    response_model=TemplateResponse,
    dependencies=[Depends(require_role("analyst", "admin"))],
)
def update_template(
    template_id: str,
    payload: TemplateUpdateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with get_db_session() as session:
        service = ProcessService(session)
        tpl = service.update_template(
            template_id,
            name=payload.name,
            description=payload.description,
            version=payload.version,
            definition=payload.definition,
            is_active=payload.is_active,
        )
        if not tpl:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_id}' not found",
            )
        session.commit()
        return {
            "id": tpl.id,
            "name": tpl.name,
            "description": tpl.description,
            "version": tpl.version,
            "definition": tpl.definition,
            "is_active": tpl.is_active,
            "created_at": tpl.created_at.isoformat() if tpl.created_at else "",
        }


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("admin"))],
)
def delete_template(
    template_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    with get_db_session() as session:
        service = ProcessService(session)
        deleted = service.delete_template(template_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_id}' not found",
            )
        session.commit()


# ---------------------------------------------------------------------------
# Process Instance Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/instances",
    response_model=InstanceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("analyst", "admin"))],
)
def start_instance(
    payload: InstanceStartRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with get_db_session() as session:
        service = ProcessService(session)
        try:
            inst = service.start_process(
                template_id=payload.template_id,
                title=payload.title,
                context=payload.context,
                created_by_id=str(current_user["id"]),
            )
            tasks = service.get_instance_tasks(inst.id)
            return {
                "id": inst.id,
                "template_id": inst.template_id,
                "title": inst.title,
                "status": inst.status,
                "context": inst.context,
                "created_by_id": inst.created_by_id,
                "created_at": inst.created_at.isoformat() if inst.created_at else "",
                "tasks": [
                    {
                        "id": t.id,
                        "instance_id": t.instance_id,
                        "position": t.position,
                        "name": t.name,
                        "description": t.description,
                        "assignee_id": t.assignee_id,
                        "assignee_role": t.assignee_role,
                        "status": t.status,
                        "result": t.result,
                        "created_at": t.created_at.isoformat() if t.created_at else "",
                    }
                    for t in tasks
                ],
            }
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )


@router.get(
    "/instances",
    response_model=list[InstanceResponse],
    dependencies=[Depends(require_role("viewer", "analyst", "admin"))],
)
def list_instances(
    status_filter: Optional[str] = Query(None, alias="status"),
    template_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    with get_db_session() as session:
        service = ProcessService(session)
        instances = service.list_instances(
            status=status_filter, template_id=template_id, limit=limit, offset=offset
        )
        return [
            {
                "id": inst.id,
                "template_id": inst.template_id,
                "title": inst.title,
                "status": inst.status,
                "context": inst.context,
                "created_by_id": inst.created_by_id,
                "created_at": inst.created_at.isoformat() if inst.created_at else "",
            }
            for inst in instances
        ]


@router.get(
    "/instances/{instance_id}",
    response_model=InstanceResponse,
    dependencies=[Depends(require_role("viewer", "analyst", "admin"))],
)
def get_instance(
    instance_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with get_db_session() as session:
        service = ProcessService(session)
        inst = service.get_instance(instance_id)
        if not inst:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Process instance '{instance_id}' not found",
            )
        tasks = service.get_instance_tasks(inst.id)
        return {
            "id": inst.id,
            "template_id": inst.template_id,
            "title": inst.title,
            "status": inst.status,
            "context": inst.context,
            "created_by_id": inst.created_by_id,
            "created_at": inst.created_at.isoformat() if inst.created_at else "",
            "tasks": [
                {
                    "id": t.id,
                    "instance_id": t.instance_id,
                    "position": t.position,
                    "name": t.name,
                    "description": t.description,
                    "assignee_id": t.assignee_id,
                    "assignee_role": t.assignee_role,
                    "status": t.status,
                    "result": t.result,
                    "created_at": t.created_at.isoformat() if t.created_at else "",
                }
                for t in tasks
            ],
        }


@router.post(
    "/instances/{instance_id}/transition",
    response_model=InstanceResponse,
    dependencies=[Depends(require_role("analyst", "admin"))],
)
def transition_instance(
    instance_id: str,
    payload: InstanceTransitionRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with get_db_session() as session:
        service = ProcessService(session)
        try:
            inst = service.transition_instance(
                instance_id=instance_id,
                target_status=payload.status,
                context_update=payload.context,
            )
            return {
                "id": inst.id,
                "template_id": inst.template_id,
                "title": inst.title,
                "status": inst.status,
                "context": inst.context,
                "created_by_id": inst.created_by_id,
                "created_at": inst.created_at.isoformat() if inst.created_at else "",
            }
        except ValueError as exc:
            msg = str(exc)
            status_code = (
                status.HTTP_404_NOT_FOUND
                if "not found" in msg.lower()
                else status.HTTP_400_BAD_REQUEST
            )
            raise HTTPException(status_code=status_code, detail=msg)


# ---------------------------------------------------------------------------
# Task Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/instances/{instance_id}/tasks",
    response_model=list[TaskResponse],
    dependencies=[Depends(require_role("viewer", "analyst", "admin"))],
)
def get_instance_tasks(
    instance_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    with get_db_session() as session:
        service = ProcessService(session)
        tasks = service.get_instance_tasks(instance_id)
        return [
            {
                "id": t.id,
                "instance_id": t.instance_id,
                "position": t.position,
                "name": t.name,
                "description": t.description,
                "assignee_id": t.assignee_id,
                "assignee_role": t.assignee_role,
                "status": t.status,
                "result": t.result,
                "created_at": t.created_at.isoformat() if t.created_at else "",
            }
            for t in tasks
        ]


@router.patch(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    dependencies=[Depends(require_role("analyst", "admin"))],
)
def update_task(
    task_id: str,
    payload: TaskUpdateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with get_db_session() as session:
        service = ProcessService(session)
        try:
            task = service.update_task_status(
                task_id=task_id,
                target_status=payload.status,
                result=payload.result,
            )
            return {
                "id": task.id,
                "instance_id": task.instance_id,
                "position": task.position,
                "name": task.name,
                "description": task.description,
                "assignee_id": task.assignee_id,
                "assignee_role": task.assignee_role,
                "status": task.status,
                "result": task.result,
                "created_at": task.created_at.isoformat() if task.created_at else "",
            }
        except ValueError as exc:
            msg = str(exc)
            status_code = (
                status.HTTP_404_NOT_FOUND
                if "not found" in msg.lower()
                else status.HTTP_400_BAD_REQUEST
            )
            raise HTTPException(status_code=status_code, detail=msg)


# ---------------------------------------------------------------------------
# Approval Request Endpoints
# ---------------------------------------------------------------------------


@approvals_router.post(
    "",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("viewer", "analyst", "admin"))],
)
def create_approval_request(
    payload: ApprovalCreateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with get_db_session() as session:
        service = ApprovalService(session)
        req = service.request_approval(
            target_type=payload.target_type,
            target_id=payload.target_id,
            action=payload.action,
            requested_by_id=str(current_user["id"]),
        )
        return {
            "id": req.id,
            "target_type": req.target_type,
            "target_id": req.target_id,
            "action": req.action,
            "requested_by_id": req.requested_by_id,
            "status": req.status,
            "reviewed_by_id": req.reviewed_by_id,
            "comment": req.comment,
            "created_at": req.created_at.isoformat() if req.created_at else "",
        }


@approvals_router.get(
    "",
    response_model=list[ApprovalResponse],
    dependencies=[Depends(require_role("viewer", "analyst", "admin"))],
)
def list_approvals(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    with get_db_session() as session:
        service = ApprovalService(session)
        reqs = service.list_requests(status=status_filter, limit=limit, offset=offset)
        return [
            {
                "id": r.id,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "action": r.action,
                "requested_by_id": r.requested_by_id,
                "status": r.status,
                "reviewed_by_id": r.reviewed_by_id,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in reqs
        ]


@approvals_router.post(
    "/{request_id}/approve",
    response_model=ApprovalResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
def approve_request(
    request_id: str,
    payload: ApprovalDecisionRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with get_db_session() as session:
        service = ApprovalService(session)
        try:
            req = service.approve(
                request_id=request_id,
                reviewed_by_id=str(current_user["id"]),
                comment=payload.comment,
            )
            return {
                "id": req.id,
                "target_type": req.target_type,
                "target_id": req.target_id,
                "action": req.action,
                "requested_by_id": req.requested_by_id,
                "status": req.status,
                "reviewed_by_id": req.reviewed_by_id,
                "comment": req.comment,
                "created_at": req.created_at.isoformat() if req.created_at else "",
            }
        except ValueError as exc:
            msg = str(exc)
            status_code = (
                status.HTTP_404_NOT_FOUND
                if "not found" in msg.lower()
                else status.HTTP_400_BAD_REQUEST
            )
            raise HTTPException(status_code=status_code, detail=msg)


@approvals_router.post(
    "/{request_id}/reject",
    response_model=ApprovalResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
def reject_request(
    request_id: str,
    payload: ApprovalDecisionRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with get_db_session() as session:
        service = ApprovalService(session)
        try:
            req = service.reject(
                request_id=request_id,
                reviewed_by_id=str(current_user["id"]),
                comment=payload.comment,
            )
            return {
                "id": req.id,
                "target_type": req.target_type,
                "target_id": req.target_id,
                "action": req.action,
                "requested_by_id": req.requested_by_id,
                "status": req.status,
                "reviewed_by_id": req.reviewed_by_id,
                "comment": req.comment,
                "created_at": req.created_at.isoformat() if req.created_at else "",
            }
        except ValueError as exc:
            msg = str(exc)
            status_code = (
                status.HTTP_404_NOT_FOUND
                if "not found" in msg.lower()
                else status.HTTP_400_BAD_REQUEST
            )
            raise HTTPException(status_code=status_code, detail=msg)
