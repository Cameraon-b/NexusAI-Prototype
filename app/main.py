from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import connect, init_db, log_action, participant_id, risk_id, rows_to_dicts, service_id
from .models import (
    ApprovalCreate,
    ApprovalOut,
    ApprovalPatch,
    DashboardOut,
    LogOut,
    MessageCreate,
    MessageOut,
    MessagePatch,
    NoticeCreate,
    NoticeOut,
    NoticePatch,
    ParticipantOut,
    ReviewCreate,
    ReviewOut,
    ReviewPatch,
    RiskLevelOut,
    ServiceCreate,
    ServiceOut,
    ServicePatch,
    TaskCreate,
    TaskOut,
    TaskPatch,
    approval_timestamp,
)

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="NexusAI",
    description="AETHER internal operations desk for messages, tasks, reviews, notices, approvals, and append-only audit logs. It does not execute commands.",
    version="0.2.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def require_local_password(x_nexusai_password: str | None = Header(default=None)) -> None:
    """Optional simple shared password guard for private LAN v1."""
    import os

    expected = os.getenv("NEXUSAI_ADMIN_PASSWORD", "")
    if expected and not secrets.compare_digest(x_nexusai_password or "", expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid NexusAI password")


def fetch_one(sql: str, params: tuple[Any, ...]) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(sql, params).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Record not found")
    return dict(row)


def message_select(where: str = "", params: tuple[Any, ...] = (), limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT m.id, ps.display_name AS "from", pr.display_name AS "to", m.subject, m.body,
               rl.name AS risk_level, m.status, m.requires_approval,
               COALESCE(pa.display_name, '') AS approved_by, COALESCE(m.approved_at, '') AS approved_at,
               COALESCE(mr.delivery_status, '') AS delivery_status,
               m.created_at, m.updated_at
        FROM messages m
        JOIN participants ps ON ps.id = m.sender_id
        LEFT JOIN risk_levels rl ON rl.id = m.risk_level_id
        LEFT JOIN message_recipients mr ON mr.message_id = m.id
        LEFT JOIN participants pr ON pr.id = mr.recipient_id
        LEFT JOIN participants pa ON pa.id = m.approved_by_id
    """
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY m.created_at DESC, m.id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with connect() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


def task_select(where: str = "", params: tuple[Any, ...] = (), limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT t.id, t.title, t.description, pc.display_name AS created_by,
               COALESCE(pa.display_name, '') AS assigned_to, rl.name AS risk_level,
               t.status, COALESCE(t.completion_notes, '') AS completion_notes,
               COALESCE(t.blocked_reason, '') AS blocked_reason,
               t.created_at, t.updated_at, COALESCE(t.completed_at, '') AS completed_at
        FROM tasks t
        JOIN participants pc ON pc.id = t.created_by_id
        LEFT JOIN participants pa ON pa.id = t.assigned_to_id
        LEFT JOIN risk_levels rl ON rl.id = t.risk_level_id
    """
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY t.created_at DESC, t.id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with connect() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


def approval_select(where: str = "", params: tuple[Any, ...] = (), limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT a.id, pr.display_name AS requested_by, pf.display_name AS requested_for,
               a.target_type, a.target_id, a.action_type, a.action_summary,
               COALESCE(a.proposed_command, '') AS proposed_command, rl.name AS risk_level,
               COALESCE(a.reason, '') AS reason, a.status,
               COALESCE(pd.display_name, '') AS approved_by,
               COALESCE(a.decided_at, '') AS approved_at,
               CASE WHEN a.status = 'rejected' THEN COALESCE(a.decision_notes, '') ELSE '' END AS rejection_reason,
               COALESCE(a.decision_notes, '') AS decision_notes,
               a.created_at, a.updated_at
        FROM approval_requests a
        JOIN participants pr ON pr.id = a.requested_by_id
        JOIN participants pf ON pf.id = a.requested_for_id
        LEFT JOIN participants pd ON pd.id = a.decided_by_id
        LEFT JOIN risk_levels rl ON rl.id = a.risk_level_id
    """
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY a.requested_at DESC, a.id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with connect() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


def review_select(where: str = "", params: tuple[Any, ...] = (), limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT r.id, r.title, r.body, pb.display_name AS requested_by,
               COALESCE(rv.display_name, '') AS reviewer, r.target_type, COALESCE(r.target_ref, '') AS target_ref,
               rl.name AS risk_level, r.status, COALESCE(r.review_notes, '') AS review_notes,
               r.created_at, r.updated_at, COALESCE(r.completed_at, '') AS completed_at
        FROM review_requests r
        JOIN participants pb ON pb.id = r.requested_by_id
        LEFT JOIN participants rv ON rv.id = r.reviewer_id
        LEFT JOIN risk_levels rl ON rl.id = r.risk_level_id
    """
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY r.created_at DESC, r.id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with connect() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


def notice_select(where: str = "", params: tuple[Any, ...] = (), limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT n.id, COALESCE(s.name, '') AS service, COALESCE(p.display_name, '') AS source,
               n.severity, n.title, n.body, n.status, rl.name AS risk_level,
               n.created_at, n.updated_at, COALESCE(n.resolved_at, '') AS resolved_at
        FROM system_notices n
        LEFT JOIN services s ON s.id = n.service_id
        LEFT JOIN participants p ON p.id = n.source_participant_id
        LEFT JOIN risk_levels rl ON rl.id = n.risk_level_id
    """
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY n.created_at DESC, n.id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with connect() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


def log_select(limit: int = 200) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT l.id, l.created_at AS timestamp, COALESCE(p.display_name, 'System') AS actor,
                       l.action_type, l.entity_type AS target_type, l.entity_id AS target_id,
                       l.summary, COALESCE(l.before_json, '') AS before_json, COALESCE(l.after_json, '') AS after_json
                FROM action_logs l
                LEFT JOIN participants p ON p.id = l.actor_id
                ORDER BY l.created_at DESC, l.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        )
    return rows


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/{page_name}", include_in_schema=False)
def ui_page(page_name: str) -> FileResponse:
    allowed = {"messages", "tasks", "approvals", "reviews", "notices", "agents", "participants", "logs", "services"}
    if page_name not in allowed:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "NexusAI", "command_execution": "disabled", "safety": "Approval does not equal execution."}


@app.get("/api/dashboard", response_model=DashboardOut)
def dashboard(_: None = Depends(require_local_password)) -> dict[str, Any]:
    return {
        "open_messages": message_select("m.status IN ('unread','open','delivered')", limit=10),
        "open_tasks": task_select("t.status IN ('open','in_progress','blocked')", limit=10),
        "pending_approvals": approval_select("a.status = 'pending'", limit=10),
        "open_reviews": review_select("r.status IN ('open','in_progress')", limit=10),
        "active_notices": notice_select("n.status IN ('active','acknowledged')", limit=10),
        "recent_logs": log_select(15),
    }


@app.get("/api/participants", response_model=list[ParticipantOut])
def participants(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM participants ORDER BY is_active DESC, id ASC").fetchall())


@app.get("/api/agents", response_model=list[ParticipantOut])
def agents(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    return participants(_)


@app.get("/api/risk-levels", response_model=list[RiskLevelOut])
def risk_levels(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM risk_levels ORDER BY sort_order ASC, id ASC").fetchall())


@app.get("/api/messages", response_model=list[MessageOut])
def messages(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    return message_select()


@app.get("/api/messages/{message_id}", response_model=MessageOut)
def message(message_id: int, _: None = Depends(require_local_password)) -> dict[str, Any]:
    rows = message_select("m.id = ?", (message_id,), 1)
    if not rows:
        raise HTTPException(status_code=404, detail="Message not found")
    return rows[0]


@app.post("/api/messages", response_model=MessageOut, status_code=201)
def create_message(payload: MessageCreate, _: None = Depends(require_local_password)) -> dict[str, Any]:
    with connect() as conn:
        sender = participant_id(conn, payload.from_)
        recipient = participant_id(conn, payload.to)
        is_ai_to_ai = payload.from_.lower() not in {"cameron", "system"} and payload.to.lower() not in {"cameron", "system"}
        requires_approval = payload.requires_approval or is_ai_to_ai
        status_value = "pending_approval" if requires_approval else payload.status.value
        cur = conn.execute(
            """
            INSERT INTO messages (sender_id, subject, body, risk_level_id, status, requires_approval)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (sender, payload.subject, payload.body, risk_id(conn, "AI-TO-AI PENDING" if requires_approval else payload.risk_level.value), status_value, int(requires_approval)),
        )
        item_id = int(cur.lastrowid)
        delivery_status = "pending_approval" if requires_approval else "delivered"
        conn.execute(
            "INSERT INTO message_recipients (message_id, recipient_id, delivery_status, delivered_at) VALUES (?, ?, ?, CASE WHEN ? THEN NULL ELSE CURRENT_TIMESTAMP END)",
            (item_id, recipient, delivery_status, int(requires_approval)),
        )
        log_action(conn, sender, "create", "message", item_id, f"Message to {payload.to}: {payload.subject}")
        if requires_approval:
            cameron = participant_id(conn, "Cameron")
            approval = conn.execute(
                """
                INSERT INTO approval_requests (requested_by_id, requested_for_id, target_type, target_id, action_type, action_summary, reason, risk_level_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sender, cameron, "message", item_id, "ai_to_ai_delivery", f"Approve AI-to-AI message delivery: {payload.subject}", "AI-to-AI messages require Cameron approval by default.", risk_id(conn, "AI-TO-AI PENDING"), "pending"),
            )
            log_action(conn, sender, "create", "approval", int(approval.lastrowid), f"AI-to-AI delivery approval requested for message #{item_id}.")
    return message(item_id)


@app.patch("/api/messages/{message_id}", response_model=MessageOut)
def patch_message(message_id: int, payload: MessagePatch, _: None = Depends(require_local_password)) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True, by_alias=True)
    if not updates:
        return message(message_id)
    with connect() as conn:
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Message not found")
        if "to" in updates:
            conn.execute("DELETE FROM message_recipients WHERE message_id = ?", (message_id,))
            conn.execute("INSERT INTO message_recipients (message_id, recipient_id, delivery_status, delivered_at) VALUES (?, ?, 'delivered', CURRENT_TIMESTAMP)", (message_id, participant_id(conn, updates.pop("to"))))
        set_parts, values = [], []
        field_map = {"risk_level": "risk_level_id", "approved_by": "approved_by_id"}
        for key, value in updates.items():
            col = field_map.get(key, key)
            if key == "risk_level":
                value = risk_id(conn, value.value if hasattr(value, "value") else str(value))
            elif key == "approved_by":
                value = participant_id(conn, str(value))
            elif hasattr(value, "value"):
                value = value.value
            elif isinstance(value, bool):
                value = int(value)
            set_parts.append(f"{col} = ?")
            values.append(value)
        if updates.get("status") in {"delivered", "acknowledged", "completed"}:
            set_parts.append("approved_at = COALESCE(approved_at, CURRENT_TIMESTAMP)")
        if set_parts:
            values.append(message_id)
            conn.execute(f"UPDATE messages SET {', '.join(set_parts)} WHERE id = ?", values)
        log_action(conn, row["sender_id"], "update", "message", message_id, "Updated message status/detail.")
    return message(message_id)


@app.get("/api/tasks", response_model=list[TaskOut])
def tasks(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    return task_select()


@app.get("/api/tasks/{task_id}", response_model=TaskOut)
def task(task_id: int, _: None = Depends(require_local_password)) -> dict[str, Any]:
    rows = task_select("t.id = ?", (task_id,), 1)
    if not rows:
        raise HTTPException(status_code=404, detail="Task not found")
    return rows[0]


@app.post("/api/tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate, _: None = Depends(require_local_password)) -> dict[str, Any]:
    with connect() as conn:
        created_by = participant_id(conn, payload.created_by)
        assigned_to = participant_id(conn, payload.assigned_to)
        cur = conn.execute(
            """
            INSERT INTO tasks (title, description, created_by_id, assigned_to_id, risk_level_id, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (payload.title, payload.description, created_by, assigned_to, risk_id(conn, payload.risk_level.value), payload.status.value),
        )
        item_id = int(cur.lastrowid)
        log_action(conn, created_by, "create", "task", item_id, f"Task for {payload.assigned_to}: {payload.title}")
    return task(item_id)


@app.patch("/api/tasks/{task_id}", response_model=TaskOut)
def patch_task(task_id: int, payload: TaskPatch, _: None = Depends(require_local_password)) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return task(task_id)
    with connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        set_parts, values = [], []
        for key, value in updates.items():
            col = key
            if key == "assigned_to":
                col = "assigned_to_id"
                value = participant_id(conn, str(value))
            elif key == "risk_level":
                col = "risk_level_id"
                value = risk_id(conn, value.value if hasattr(value, "value") else str(value))
            elif hasattr(value, "value"):
                value = value.value
            set_parts.append(f"{col} = ?")
            values.append(value)
        if updates.get("status") == "completed":
            set_parts.append("completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP)")
        values.append(task_id)
        conn.execute(f"UPDATE tasks SET {', '.join(set_parts)} WHERE id = ?", values)
        log_action(conn, row["assigned_to_id"] or row["created_by_id"], "update", "task", task_id, f"Updated task: {task_id}")
    return task(task_id)


@app.get("/api/approvals", response_model=list[ApprovalOut])
def approvals(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    return approval_select()


@app.get("/api/approvals/{approval_id}", response_model=ApprovalOut)
def approval(approval_id: int, _: None = Depends(require_local_password)) -> dict[str, Any]:
    rows = approval_select("a.id = ?", (approval_id,), 1)
    if not rows:
        raise HTTPException(status_code=404, detail="Approval not found")
    return rows[0]


@app.post("/api/approvals", response_model=ApprovalOut, status_code=201)
def create_approval(payload: ApprovalCreate, _: None = Depends(require_local_password)) -> dict[str, Any]:
    with connect() as conn:
        requested_by = participant_id(conn, payload.requested_by)
        requested_for = participant_id(conn, payload.requested_for)
        cur = conn.execute(
            """
            INSERT INTO approval_requests (requested_by_id, requested_for_id, target_type, target_id, action_type, action_summary, proposed_command, reason, risk_level_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (requested_by, requested_for, payload.target_type, payload.target_id, payload.action_type, payload.action_summary, payload.proposed_command, payload.reason, risk_id(conn, payload.risk_level.value), payload.status.value),
        )
        item_id = int(cur.lastrowid)
        log_action(conn, requested_by, "create", "approval", item_id, f"Approval requested from {payload.requested_for}: {payload.action_summary}")
    return approval(item_id)


@app.patch("/api/approvals/{approval_id}", response_model=ApprovalOut)
def patch_approval(approval_id: int, payload: ApprovalPatch, _: None = Depends(require_local_password)) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if "approved_by" in updates and "decision_notes" not in updates and updates.get("rejection_reason"):
        updates["decision_notes"] = updates["rejection_reason"]
    if not updates:
        return approval(approval_id)
    with connect() as conn:
        row = conn.execute("SELECT * FROM approval_requests WHERE id = ?", (approval_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Approval not found")
        set_parts, values = [], []
        for key, value in updates.items():
            if key in {"approved_by", "requested_for"}:
                col = "decided_by_id" if key == "approved_by" else "requested_for_id"
                value = participant_id(conn, str(value))
            elif key == "risk_level":
                col = "risk_level_id"
                value = risk_id(conn, value.value if hasattr(value, "value") else str(value))
            elif key == "rejection_reason":
                col = "decision_notes"
            else:
                col = key
                if hasattr(value, "value"):
                    value = value.value
            set_parts.append(f"{col} = ?")
            values.append(value)
        if updates.get("status") in {"approved", "rejected"}:
            set_parts.append("decided_at = COALESCE(decided_at, ?)")
            values.append(approval_timestamp("approved"))
        values.append(approval_id)
        conn.execute(f"UPDATE approval_requests SET {', '.join(set_parts)} WHERE id = ?", values)
        patched = conn.execute("SELECT status, target_type, target_id, decided_by_id FROM approval_requests WHERE id = ?", (approval_id,)).fetchone()
        if patched["status"] == "approved" and patched["target_type"] == "message" and patched["target_id"]:
            conn.execute("UPDATE messages SET status='delivered', requires_approval=0, approved_by_id=?, approved_at=CURRENT_TIMESTAMP WHERE id=?", (patched["decided_by_id"], patched["target_id"]))
            conn.execute("UPDATE message_recipients SET delivery_status='delivered', delivered_at=CURRENT_TIMESTAMP WHERE message_id=?", (patched["target_id"],))
        log_action(conn, row["requested_by_id"], "update", "approval", approval_id, "Approval decision/status recorded only; no command executed.")
    return approval(approval_id)


@app.get("/api/reviews", response_model=list[ReviewOut])
def reviews(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    return review_select()


@app.get("/api/reviews/{review_id}", response_model=ReviewOut)
def review(review_id: int, _: None = Depends(require_local_password)) -> dict[str, Any]:
    rows = review_select("r.id = ?", (review_id,), 1)
    if not rows:
        raise HTTPException(status_code=404, detail="Review not found")
    return rows[0]


@app.post("/api/reviews", response_model=ReviewOut, status_code=201)
def create_review(payload: ReviewCreate, _: None = Depends(require_local_password)) -> dict[str, Any]:
    with connect() as conn:
        requested_by = participant_id(conn, payload.requested_by)
        reviewer = participant_id(conn, payload.reviewer)
        cur = conn.execute(
            """
            INSERT INTO review_requests (title, body, requested_by_id, reviewer_id, target_type, target_ref, risk_level_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (payload.title, payload.body, requested_by, reviewer, payload.target_type, payload.target_ref, risk_id(conn, payload.risk_level.value), payload.status.value),
        )
        item_id = int(cur.lastrowid)
        log_action(conn, requested_by, "create", "review", item_id, f"Review requested from {payload.reviewer}: {payload.title}")
    return review(item_id)


@app.patch("/api/reviews/{review_id}", response_model=ReviewOut)
def patch_review(review_id: int, payload: ReviewPatch, _: None = Depends(require_local_password)) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return review(review_id)
    with connect() as conn:
        row = conn.execute("SELECT * FROM review_requests WHERE id = ?", (review_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Review not found")
        set_parts, values = [], []
        for key, value in updates.items():
            if key == "reviewer":
                col = "reviewer_id"
                value = participant_id(conn, str(value))
            elif key == "risk_level":
                col = "risk_level_id"
                value = risk_id(conn, value.value if hasattr(value, "value") else str(value))
            else:
                col = key
                if hasattr(value, "value"):
                    value = value.value
            set_parts.append(f"{col} = ?")
            values.append(value)
        if updates.get("status") == "completed":
            set_parts.append("completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP)")
        values.append(review_id)
        conn.execute(f"UPDATE review_requests SET {', '.join(set_parts)} WHERE id = ?", values)
        log_action(conn, row["reviewer_id"] or row["requested_by_id"], "update", "review", review_id, f"Updated review: {review_id}")
    return review(review_id)


@app.get("/api/notices", response_model=list[NoticeOut])
def notices(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    return notice_select()


@app.get("/api/notices/{notice_id}", response_model=NoticeOut)
def notice(notice_id: int, _: None = Depends(require_local_password)) -> dict[str, Any]:
    rows = notice_select("n.id = ?", (notice_id,), 1)
    if not rows:
        raise HTTPException(status_code=404, detail="Notice not found")
    return rows[0]


@app.post("/api/notices", response_model=NoticeOut, status_code=201)
def create_notice(payload: NoticeCreate, _: None = Depends(require_local_password)) -> dict[str, Any]:
    with connect() as conn:
        source = participant_id(conn, payload.source)
        cur = conn.execute(
            """
            INSERT INTO system_notices (service_id, source_participant_id, severity, title, body, status, risk_level_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (service_id(conn, payload.service), source, payload.severity, payload.title, payload.body, payload.status.value, risk_id(conn, payload.risk_level.value)),
        )
        item_id = int(cur.lastrowid)
        log_action(conn, source, "create", "notice", item_id, f"System notice: {payload.title}")
    return notice(item_id)


@app.patch("/api/notices/{notice_id}", response_model=NoticeOut)
def patch_notice(notice_id: int, payload: NoticePatch, _: None = Depends(require_local_password)) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return notice(notice_id)
    with connect() as conn:
        row = conn.execute("SELECT * FROM system_notices WHERE id = ?", (notice_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Notice not found")
        set_parts, values = [], []
        for key, value in updates.items():
            if key == "risk_level":
                col = "risk_level_id"
                value = risk_id(conn, value.value if hasattr(value, "value") else str(value))
            else:
                col = key
                if hasattr(value, "value"):
                    value = value.value
            set_parts.append(f"{col} = ?")
            values.append(value)
        if updates.get("status") == "resolved":
            set_parts.append("resolved_at = COALESCE(resolved_at, CURRENT_TIMESTAMP)")
        values.append(notice_id)
        conn.execute(f"UPDATE system_notices SET {', '.join(set_parts)} WHERE id = ?", values)
        log_action(conn, row["source_participant_id"], "update", "notice", notice_id, f"Updated notice: {notice_id}")
    return notice(notice_id)


@app.get("/api/services", response_model=list[ServiceOut])
def services(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM services ORDER BY is_active DESC, name ASC").fetchall())


@app.post("/api/services", response_model=ServiceOut, status_code=201)
def create_service(payload: ServiceCreate, _: None = Depends(require_local_password)) -> dict[str, Any]:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO services (name, service_type, url, host, notes, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            (payload.name, payload.service_type, payload.url, payload.host, payload.notes, int(payload.is_active)),
        )
        item_id = int(cur.lastrowid)
        log_action(conn, "System", "create", "service", item_id, f"Service registered: {payload.name}")
        return dict(conn.execute("SELECT * FROM services WHERE id = ?", (item_id,)).fetchone())


@app.patch("/api/services/{item_id}", response_model=ServiceOut)
def patch_service(item_id: int, payload: ServicePatch, _: None = Depends(require_local_password)) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if updates:
        set_parts, values = [], []
        for key, value in updates.items():
            set_parts.append(f"{key} = ?")
            values.append(int(value) if isinstance(value, bool) else value)
        values.append(item_id)
        with connect() as conn:
            conn.execute(f"UPDATE services SET {', '.join(set_parts)} WHERE id = ?", values)
            if conn.total_changes == 0:
                raise HTTPException(status_code=404, detail="Service not found")
            log_action(conn, "System", "update", "service", item_id, f"Service updated: {item_id}")
    return fetch_one("SELECT * FROM services WHERE id = ?", (item_id,))


@app.get("/api/logs", response_model=list[LogOut])
def logs(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    return log_select(200)
