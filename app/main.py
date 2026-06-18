from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import connect, init_db, log_action, rows_to_dicts
from .models import (
    AgentOut,
    ApprovalCreate,
    ApprovalOut,
    ApprovalPatch,
    DashboardOut,
    LogOut,
    MessageCreate,
    MessageOut,
    MessagePatch,
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
    description="AETHER internal communication, task, review, and approval coordination server. It does not execute commands.",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def require_local_password(x_nexusai_password: str | None = Header(default=None)) -> None:
    """Optional simple shared password guard.

    If NEXUSAI_ADMIN_PASSWORD is unset, auth is disabled for local/internal v1.
    If set, API clients must send X-NexusAI-Password.
    """
    import os

    expected = os.getenv("NEXUSAI_ADMIN_PASSWORD", "")
    if expected and not secrets.compare_digest(x_nexusai_password or "", expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid NexusAI password")


def one_or_404(table: str, item_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (item_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"{table[:-1].title()} not found")
    return normalize_row(table, dict(row))


def normalize_row(table: str, row: dict[str, Any]) -> dict[str, Any]:
    if table == "messages":
        row["from"] = row.pop("from_agent")
        row["to"] = row.pop("to_agent")
    return row


def list_rows(table: str, where: str = "", params: tuple[Any, ...] = (), limit: int | None = None) -> list[dict[str, Any]]:
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    order_col = "timestamp" if table == "action_logs" else "created_at"
    sql += f" ORDER BY {order_col} DESC, id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with connect() as conn:
        rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    return [normalize_row(table, row) for row in rows]


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/{page_name}", include_in_schema=False)
def ui_page(page_name: str) -> FileResponse:
    allowed = {"messages", "tasks", "approvals", "agents", "logs"}
    if page_name not in allowed:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "NexusAI", "command_execution": "disabled"}


@app.get("/api/dashboard", response_model=DashboardOut)
def dashboard(_: None = Depends(require_local_password)) -> dict[str, Any]:
    return {
        "open_messages": list_rows("messages", "status = ?", ("open",), 10),
        "open_tasks": list_rows("tasks", "status IN (?, ?, ?)", ("open", "in_progress", "blocked"), 10),
        "pending_approvals": list_rows("approvals", "status = ?", ("pending",), 10),
        "recent_logs": list_rows("action_logs", limit=15),
    }


@app.get("/api/agents", response_model=list[AgentOut])
def agents(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM agents ORDER BY id ASC").fetchall())


@app.get("/api/messages", response_model=list[MessageOut])
def messages(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    return list_rows("messages")


@app.post("/api/messages", response_model=MessageOut, status_code=201)
def create_message(payload: MessageCreate, _: None = Depends(require_local_password)) -> dict[str, Any]:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO messages (from_agent, to_agent, subject, body, risk_level, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (payload.from_, payload.to, payload.subject, payload.body, payload.risk_level.value, payload.status.value),
        )
        item_id = cur.lastrowid
        log_action(conn, payload.from_, "create", "message", item_id, f"Message to {payload.to}: {payload.subject}")
    return one_or_404("messages", item_id)


@app.patch("/api/messages/{message_id}", response_model=MessageOut)
def patch_message(message_id: int, payload: MessagePatch, _: None = Depends(require_local_password)) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True, by_alias=True)
    if not updates:
        return one_or_404("messages", message_id)
    column_map = {"to": "to_agent"}
    set_parts, values = [], []
    for key, value in updates.items():
        col = column_map.get(key, key)
        set_parts.append(f"{col} = ?")
        values.append(value.value if hasattr(value, "value") else value)
    values.append(message_id)
    with connect() as conn:
        conn.execute(f"UPDATE messages SET {', '.join(set_parts)} WHERE id = ?", values)
        if conn.total_changes == 0:
            raise HTTPException(status_code=404, detail="Message not found")
        row = conn.execute("SELECT from_agent, subject FROM messages WHERE id = ?", (message_id,)).fetchone()
        log_action(conn, row["from_agent"], "update", "message", message_id, f"Updated message: {row['subject']}")
    return one_or_404("messages", message_id)


@app.get("/api/tasks", response_model=list[TaskOut])
def tasks(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    return list_rows("tasks")


@app.post("/api/tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate, _: None = Depends(require_local_password)) -> dict[str, Any]:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks (title, description, created_by, assigned_to, risk_level, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (payload.title, payload.description, payload.created_by, payload.assigned_to, payload.risk_level.value, payload.status.value),
        )
        item_id = cur.lastrowid
        log_action(conn, payload.created_by, "create", "task", item_id, f"Task for {payload.assigned_to}: {payload.title}")
    return one_or_404("tasks", item_id)


@app.patch("/api/tasks/{task_id}", response_model=TaskOut)
def patch_task(task_id: int, payload: TaskPatch, _: None = Depends(require_local_password)) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return one_or_404("tasks", task_id)
    set_parts, values = [], []
    for key, value in updates.items():
        set_parts.append(f"{key} = ?")
        values.append(value.value if hasattr(value, "value") else value)
    values.append(task_id)
    with connect() as conn:
        conn.execute(f"UPDATE tasks SET {', '.join(set_parts)} WHERE id = ?", values)
        if conn.total_changes == 0:
            raise HTTPException(status_code=404, detail="Task not found")
        row = conn.execute("SELECT created_by, title FROM tasks WHERE id = ?", (task_id,)).fetchone()
        log_action(conn, row["created_by"], "update", "task", task_id, f"Updated task: {row['title']}")
    return one_or_404("tasks", task_id)


@app.get("/api/approvals", response_model=list[ApprovalOut])
def approvals(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    return list_rows("approvals")


@app.post("/api/approvals", response_model=ApprovalOut, status_code=201)
def create_approval(payload: ApprovalCreate, _: None = Depends(require_local_password)) -> dict[str, Any]:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO approvals (requested_by, requested_for, action_summary, proposed_command, risk_level, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.requested_by,
                payload.requested_for,
                payload.action_summary,
                payload.proposed_command,
                payload.risk_level.value,
                payload.reason,
                payload.status.value,
            ),
        )
        item_id = cur.lastrowid
        log_action(conn, payload.requested_by, "create", "approval", item_id, f"Approval requested from {payload.requested_for}: {payload.action_summary}")
    return one_or_404("approvals", item_id)


@app.patch("/api/approvals/{approval_id}", response_model=ApprovalOut)
def patch_approval(approval_id: int, payload: ApprovalPatch, _: None = Depends(require_local_password)) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates and str(updates["status"]) == "approved" and not updates.get("approved_at"):
        updates["approved_at"] = approval_timestamp("approved")
    if not updates:
        return one_or_404("approvals", approval_id)
    set_parts, values = [], []
    for key, value in updates.items():
        set_parts.append(f"{key} = ?")
        values.append(value.value if hasattr(value, "value") else value)
    values.append(approval_id)
    with connect() as conn:
        conn.execute(f"UPDATE approvals SET {', '.join(set_parts)} WHERE id = ?", values)
        if conn.total_changes == 0:
            raise HTTPException(status_code=404, detail="Approval not found")
        row = conn.execute("SELECT requested_by, action_summary, status FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        log_action(conn, row["requested_by"], "update", "approval", approval_id, f"Approval {row['status']}: {row['action_summary']} — recorded only, no command executed.")
    return one_or_404("approvals", approval_id)


@app.get("/api/logs", response_model=list[LogOut])
def logs(_: None = Depends(require_local_password)) -> list[dict[str, Any]]:
    return list_rows("action_logs", limit=200)
