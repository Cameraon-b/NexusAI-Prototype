from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(StrEnum):
    safe_read_only = "SAFE / READ-ONLY"
    documentation_only = "DOCUMENTATION ONLY"
    backup_write = "BACKUP WRITE OPERATION"
    state_changing = "STATE-CHANGING / APPROVAL REQUIRED"
    restore_high_risk = "RESTORE-ONLY / HIGH RISK"
    destructive = "DESTRUCTIVE / EXPLICIT APPROVAL REQUIRED"
    ai_to_ai_pending = "AI-TO-AI PENDING"
    warning = "WARNING"
    review = "REVIEW"
    build_ui = "BUILD / UI"
    unknown = "UNKNOWN / NEEDS REVIEW"


class MessageStatus(StrEnum):
    draft = "draft"
    pending_approval = "pending_approval"
    delivered = "delivered"
    acknowledged = "acknowledged"
    completed = "completed"
    archived = "archived"
    rejected = "rejected"


class ConversationStatus(StrEnum):
    open = "open"
    paused = "paused"
    completed = "completed"
    archived = "archived"


class TaskStatus(StrEnum):
    open = "open"
    in_progress = "in_progress"
    blocked = "blocked"
    completed = "completed"
    archived = "archived"
    cancelled = "cancelled"


class ApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    archived = "archived"
    cancelled = "cancelled"


class ReviewStatus(StrEnum):
    open = "open"
    in_progress = "in_progress"
    completed = "completed"
    archived = "archived"
    cancelled = "cancelled"


class NoticeStatus(StrEnum):
    active = "active"
    acknowledged = "acknowledged"
    resolved = "resolved"
    archived = "archived"


class ParticipantOut(BaseModel):
    id: int
    name: str
    display_name: str
    participant_type: str
    role_description: str = ""
    is_active: bool
    created_at: str
    updated_at: str


class RiskLevelOut(BaseModel):
    id: int
    name: str
    description: str = ""
    sort_order: int


class MessageCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    subject: str
    body: str
    risk_level: RiskLevel = RiskLevel.documentation_only
    status: MessageStatus = MessageStatus.delivered
    requires_approval: bool = False
    conversation_id: Optional[int] = None
    parent_message_id: Optional[int] = None


class MessageReadCreate(BaseModel):
    participant: str


class MessageReplyCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    body: str
    risk_level: RiskLevel = RiskLevel.documentation_only


class MessagePatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    to: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    status: Optional[MessageStatus] = None
    requires_approval: Optional[bool] = None
    approved_by: Optional[str] = None


class MessageOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    from_: str = Field(alias="from")
    to: str
    subject: str
    body: str
    risk_level: RiskLevel
    requested_risk_level: Optional[RiskLevel] = None
    conversation_id: Optional[int] = None
    parent_message_id: Optional[int] = None
    status: MessageStatus
    requires_approval: bool = False
    approved_by: str = ""
    approved_at: str = ""
    delivery_status: str = ""
    created_at: str
    updated_at: str


class ConversationCreate(BaseModel):
    title: str
    created_by: str = "System"
    max_turns: int = 6
    summary: str = ""
    status: ConversationStatus = ConversationStatus.open


class ConversationPatch(BaseModel):
    title: Optional[str] = None
    status: Optional[ConversationStatus] = None
    max_turns: Optional[int] = None
    summary: Optional[str] = None


class ConversationOut(BaseModel):
    id: int
    title: str
    status: ConversationStatus
    created_by: str = ""
    max_turns: int
    turn_count: int
    summary: str = ""
    created_at: str
    updated_at: str
    completed_at: str = ""


class AgentInboxOut(BaseModel):
    participant: str
    limit: int
    messages: list[MessageOut]


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
    blocked_reason: Optional[str] = None


class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    created_by: str
    assigned_to: str
    risk_level: RiskLevel
    status: TaskStatus
    completion_notes: str = ""
    blocked_reason: str = ""
    created_at: str
    updated_at: str
    completed_at: str = ""


class ApprovalCreate(BaseModel):
    requested_by: str
    requested_for: str
    action_summary: str
    proposed_command: str = ""
    risk_level: RiskLevel = RiskLevel.unknown
    reason: str = ""
    status: ApprovalStatus = ApprovalStatus.pending
    target_type: str = "general"
    target_id: Optional[int] = None
    action_type: str = "requested_action"


class ApprovalPatch(BaseModel):
    requested_for: Optional[str] = None
    action_summary: Optional[str] = None
    proposed_command: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    reason: Optional[str] = None
    status: Optional[ApprovalStatus] = None
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    decision_notes: Optional[str] = None


class ApprovalOut(BaseModel):
    id: int
    requested_by: str
    requested_for: str
    target_type: str = "general"
    target_id: Optional[int] = None
    action_type: str = "requested_action"
    action_summary: str
    proposed_command: str = ""
    risk_level: RiskLevel
    reason: str = ""
    status: ApprovalStatus
    approved_by: str = ""
    approved_at: str = ""
    rejection_reason: str = ""
    decision_notes: str = ""
    created_at: str
    updated_at: str


class ReviewCreate(BaseModel):
    title: str
    body: str
    requested_by: str
    reviewer: str
    target_type: str = "general"
    target_ref: str = ""
    risk_level: RiskLevel = RiskLevel.review
    status: ReviewStatus = ReviewStatus.open


class ReviewPatch(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    reviewer: Optional[str] = None
    target_type: Optional[str] = None
    target_ref: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    status: Optional[ReviewStatus] = None
    review_notes: Optional[str] = None


class ReviewOut(BaseModel):
    id: int
    title: str
    body: str
    requested_by: str
    reviewer: str
    target_type: str
    target_ref: str = ""
    risk_level: RiskLevel
    status: ReviewStatus
    review_notes: str = ""
    created_at: str
    updated_at: str
    completed_at: str = ""


class NoticeCreate(BaseModel):
    service: str = ""
    source: str = "System"
    severity: str = "info"
    title: str
    body: str
    status: NoticeStatus = NoticeStatus.active
    risk_level: RiskLevel = RiskLevel.warning


class NoticePatch(BaseModel):
    severity: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    status: Optional[NoticeStatus] = None
    risk_level: Optional[RiskLevel] = None


class NoticeOut(BaseModel):
    id: int
    service: str = ""
    source: str = ""
    severity: str
    title: str
    body: str
    status: NoticeStatus
    risk_level: RiskLevel
    created_at: str
    updated_at: str
    resolved_at: str = ""


class ServiceCreate(BaseModel):
    name: str
    service_type: str = ""
    url: str = ""
    host: str = ""
    notes: str = ""
    is_active: bool = True


class ServicePatch(BaseModel):
    service_type: Optional[str] = None
    url: Optional[str] = None
    host: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ServiceOut(BaseModel):
    id: int
    name: str
    service_type: str = ""
    url: str = ""
    host: str = ""
    notes: str = ""
    is_active: bool
    created_at: str
    updated_at: str


class LogOut(BaseModel):
    id: int
    timestamp: str
    actor: str
    action_type: str
    target_type: str
    target_id: int | None = None
    summary: str
    before_json: str = ""
    after_json: str = ""


class DashboardOut(BaseModel):
    open_messages: list[MessageOut]
    open_tasks: list[TaskOut]
    pending_approvals: list[ApprovalOut]
    open_reviews: list[ReviewOut]
    active_notices: list[NoticeOut]
    recent_logs: list[LogOut]


def approval_timestamp(status: ApprovalStatus | str | None) -> str:
    if status == ApprovalStatus.approved or status == "approved":
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return ""
