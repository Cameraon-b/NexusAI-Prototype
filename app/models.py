from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class RiskLevel(StrEnum):
    safe_read_only = "SAFE / READ-ONLY"
    documentation_only = "DOCUMENTATION ONLY"
    backup_write = "BACKUP WRITE OPERATION"
    state_changing = "STATE-CHANGING / APPROVAL REQUIRED"
    restore_high_risk = "RESTORE-ONLY / HIGH RISK"
    destructive = "DESTRUCTIVE / EXPLICIT APPROVAL REQUIRED"
    unknown = "UNKNOWN / NEEDS REVIEW"


class MessageStatus(StrEnum):
    open = "open"
    acknowledged = "acknowledged"
    completed = "completed"
    archived = "archived"


class TaskStatus(StrEnum):
    open = "open"
    in_progress = "in_progress"
    blocked = "blocked"
    completed = "completed"
    cancelled = "cancelled"


class ApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class AgentOut(BaseModel):
    id: int
    name: str
    description: str = ""
    created_at: str


class MessageCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    subject: str
    body: str
    risk_level: RiskLevel = RiskLevel.unknown
    status: MessageStatus = MessageStatus.open


class MessagePatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    to: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    status: Optional[MessageStatus] = None


class MessageOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    from_: str = Field(alias="from")
    to: str
    subject: str
    body: str
    risk_level: RiskLevel
    status: MessageStatus
    created_at: str
    updated_at: str


class TaskCreate(BaseModel):
    title: str
    description: str
    created_by: str
    assigned_to: str
    risk_level: RiskLevel = RiskLevel.unknown
    status: TaskStatus = TaskStatus.open


class TaskPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    status: Optional[TaskStatus] = None
    completion_notes: Optional[str] = None


class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    created_by: str
    assigned_to: str
    risk_level: RiskLevel
    status: TaskStatus
    created_at: str
    updated_at: str
    completion_notes: str = ""


class ApprovalCreate(BaseModel):
    requested_by: str
    requested_for: str
    action_summary: str
    proposed_command: str
    risk_level: RiskLevel = RiskLevel.unknown
    reason: str
    status: ApprovalStatus = ApprovalStatus.pending


class ApprovalPatch(BaseModel):
    requested_for: Optional[str] = None
    action_summary: Optional[str] = None
    proposed_command: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    reason: Optional[str] = None
    status: Optional[ApprovalStatus] = None
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None


class ApprovalOut(BaseModel):
    id: int
    requested_by: str
    requested_for: str
    action_summary: str
    proposed_command: str
    risk_level: RiskLevel
    reason: str
    status: ApprovalStatus
    approved_by: str = ""
    approved_at: str = ""
    rejection_reason: str = ""
    created_at: str
    updated_at: str


class LogOut(BaseModel):
    id: int
    timestamp: str
    actor: str
    action_type: str
    target_type: str
    target_id: int
    summary: str


class DashboardOut(BaseModel):
    open_messages: list[MessageOut]
    open_tasks: list[TaskOut]
    pending_approvals: list[ApprovalOut]
    recent_logs: list[LogOut]


def approval_timestamp(status: ApprovalStatus | str | None) -> str:
    if status == ApprovalStatus.approved or status == "approved":
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return ""
