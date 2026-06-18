from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

DB_PATH = os.getenv("NEXUSAI_DB_PATH", "data/nexusai.db")

AGENTS = ["Cameron", "Nova", "Mira", "Hermes", "OpenClaw", "System"]

RISK_LEVELS = [
    "SAFE / READ-ONLY",
    "DOCUMENTATION ONLY",
    "BACKUP WRITE OPERATION",
    "STATE-CHANGING / APPROVAL REQUIRED",
    "RESTORE-ONLY / HIGH RISK",
    "DESTRUCTIVE / EXPLICIT APPROVAL REQUIRED",
    "UNKNOWN / NEEDS REVIEW",
]

MESSAGE_STATUSES = ["open", "acknowledged", "completed", "archived"]
TASK_STATUSES = ["open", "in_progress", "blocked", "completed", "cancelled"]
APPROVAL_STATUSES = ["pending", "approved", "rejected", "cancelled"]


def db_path() -> str:
    return os.getenv("NEXUSAI_DB_PATH", DB_PATH)


def connect() -> sqlite3.Connection:
    path = db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_agent TEXT NOT NULL,
                to_agent TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (status IN ('open','acknowledged','completed','archived')),
                CHECK (risk_level IN (
                    'SAFE / READ-ONLY',
                    'DOCUMENTATION ONLY',
                    'BACKUP WRITE OPERATION',
                    'STATE-CHANGING / APPROVAL REQUIRED',
                    'RESTORE-ONLY / HIGH RISK',
                    'DESTRUCTIVE / EXPLICIT APPROVAL REQUIRED',
                    'UNKNOWN / NEEDS REVIEW'
                ))
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                created_by TEXT NOT NULL,
                assigned_to TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                completion_notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (status IN ('open','in_progress','blocked','completed','cancelled')),
                CHECK (risk_level IN (
                    'SAFE / READ-ONLY',
                    'DOCUMENTATION ONLY',
                    'BACKUP WRITE OPERATION',
                    'STATE-CHANGING / APPROVAL REQUIRED',
                    'RESTORE-ONLY / HIGH RISK',
                    'DESTRUCTIVE / EXPLICIT APPROVAL REQUIRED',
                    'UNKNOWN / NEEDS REVIEW'
                ))
            );

            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requested_by TEXT NOT NULL,
                requested_for TEXT NOT NULL,
                action_summary TEXT NOT NULL,
                proposed_command TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                approved_by TEXT DEFAULT '',
                approved_at TEXT DEFAULT '',
                rejection_reason TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (status IN ('pending','approved','rejected','cancelled')),
                CHECK (risk_level IN (
                    'SAFE / READ-ONLY',
                    'DOCUMENTATION ONLY',
                    'BACKUP WRITE OPERATION',
                    'STATE-CHANGING / APPROVAL REQUIRED',
                    'RESTORE-ONLY / HIGH RISK',
                    'DESTRUCTIVE / EXPLICIT APPROVAL REQUIRED',
                    'UNKNOWN / NEEDS REVIEW'
                ))
            );

            CREATE TABLE IF NOT EXISTS action_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                actor TEXT NOT NULL,
                action_type TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                summary TEXT NOT NULL
            );

            CREATE TRIGGER IF NOT EXISTS messages_updated_at
            AFTER UPDATE ON messages
            BEGIN
                UPDATE messages SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;

            CREATE TRIGGER IF NOT EXISTS tasks_updated_at
            AFTER UPDATE ON tasks
            BEGIN
                UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;

            CREATE TRIGGER IF NOT EXISTS approvals_updated_at
            AFTER UPDATE ON approvals
            BEGIN
                UPDATE approvals SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
            """
        )
        seed_agents(conn)
        seed_examples(conn)


def seed_agents(conn: sqlite3.Connection) -> None:
    descriptions = {
        "Cameron": "Final approval authority and AETHER administrator.",
        "Nova": "Review partner for design, documentation, and implementation feedback.",
        "Mira": "AETHER operations assistant for documentation, planning, and safe inspection.",
        "Hermes": "Build partner and API-enabled assistant for AETHER tasks.",
        "OpenClaw": "Local AI orchestration platform and related agents.",
        "System": "Automated system notices and audit entries.",
    }
    for name in AGENTS:
        conn.execute(
            "INSERT OR IGNORE INTO agents (name, description) VALUES (?, ?)",
            (name, descriptions[name]),
        )


def seed_examples(conn: sqlite3.Connection) -> None:
    message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    if message_count == 0:
        cur = conn.execute(
            """
            INSERT INTO messages (from_agent, to_agent, subject, body, risk_level, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "Mira",
                "Nova",
                "Review Docker Service Recovery page",
                "Please review path consistency against the current Backup Strategy page.",
                "DOCUMENTATION ONLY",
                "open",
            ),
        )
        log_action(conn, "Mira", "create", "message", cur.lastrowid, "Seeded example review message from Mira to Nova.")

    task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    if task_count == 0:
        cur = conn.execute(
            """
            INSERT INTO tasks (title, description, created_by, assigned_to, risk_level, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "Review AETHER service map placeholders",
                "Identify which BookStack service map pages still need real operational detail.",
                "Hermes",
                "Mira",
                "DOCUMENTATION ONLY",
                "open",
            ),
        )
        log_action(conn, "Hermes", "create", "task", cur.lastrowid, "Seeded example documentation review task.")

    approval_count = conn.execute("SELECT COUNT(*) FROM approvals").fetchone()[0]
    if approval_count == 0:
        cur = conn.execute(
            """
            INSERT INTO approvals (requested_by, requested_for, action_summary, proposed_command, risk_level, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Hermes",
                "Cameron",
                "Restart BookStack Docker Compose service",
                "cd /home/noratheredeemer/docker/bookstack && docker compose restart",
                "STATE-CHANGING / APPROVAL REQUIRED",
                "BookStack is unreachable after restore validation.",
                "pending",
            ),
        )
        log_action(conn, "Hermes", "create", "approval", cur.lastrowid, "Seeded example approval request. No command was executed.")


def log_action(conn: sqlite3.Connection, actor: str, action_type: str, target_type: str, target_id: int, summary: str) -> None:
    conn.execute(
        """
        INSERT INTO action_logs (actor, action_type, target_type, target_id, summary)
        VALUES (?, ?, ?, ?, ?)
        """,
        (actor, action_type, target_type, target_id, summary),
    )
