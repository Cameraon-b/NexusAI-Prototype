from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

DB_PATH = os.getenv("NEXUSAI_DB_PATH", "data/nexusai.db")

PARTICIPANTS = [
    ("cameron", "Cameron", "human", "Owner/admin/final approval authority."),
    ("nova", "Nova", "ai", "ChatGPT reviewer/architect for review notes and risk review."),
    ("mira", "Mira", "ai", "OpenClaw documentation assistant for docs, planning, and safe inspection."),
    ("hermes", "Hermes", "ai", "Builder/integration assistant for AETHER tasks."),
    ("openclaw", "OpenClaw", "agent_runtime", "Local AI orchestration platform and related agents."),
    ("nora", "Nora", "service", "Host/system source of service events."),
    ("bookstack", "BookStack", "service", "Documentation system."),
    ("uptime-kuma", "Uptime Kuma", "service", "Monitoring source."),
    ("system", "System", "system", "Automated system notices and audit entries."),
]

RISK_LEVELS = [
    ("SAFE / READ-ONLY", "Safe inspection or read-only activity."),
    ("DOCUMENTATION ONLY", "Documentation, text, review, or non-operational change."),
    ("BACKUP WRITE OPERATION", "Writes backup artifacts without changing live service state."),
    ("STATE-CHANGING / APPROVAL REQUIRED", "Changes service state and requires Cameron approval."),
    ("RESTORE-ONLY / HIGH RISK", "Restore path or high-risk recovery operation."),
    ("DESTRUCTIVE / EXPLICIT APPROVAL REQUIRED", "Destructive action requiring explicit human approval."),
    ("AI-TO-AI PENDING", "AI-to-AI delivery held until Cameron approval."),
    ("WARNING", "Service/system warning requiring attention."),
    ("REVIEW", "Review request or reviewer note."),
    ("BUILD / UI", "Build or UI implementation work."),
    ("UNKNOWN / NEEDS REVIEW", "Unclear risk; must be reviewed."),
]

SERVICES = [
    ("NexusAI", "internal_app", "http://nexus.aether.lab", "Nora", "Self-hosted coordination system."),
    ("BookStack", "documentation", "http://wiki.aether.lab", "Nora", "AETHER documentation system."),
    ("Uptime Kuma", "monitoring", "", "Nora", "Monitoring and alert source."),
]

MESSAGE_STATUSES = ["unread", "open", "pending_approval", "delivered", "acknowledged", "completed", "archived"]
TASK_STATUSES = ["open", "in_progress", "blocked", "completed", "archived", "cancelled"]
APPROVAL_STATUSES = ["pending", "approved", "rejected", "archived", "cancelled"]
REVIEW_STATUSES = ["open", "in_progress", "completed", "archived", "cancelled"]
NOTICE_STATUSES = ["active", "acknowledged", "resolved", "archived"]


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


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.DatabaseError:
        return set()


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def archive_legacy_schema(conn: sqlite3.Connection) -> None:
    """Preserve the earlier prototype tables before creating the designed schema.

    The v0 prototype used text agent columns such as messages.from_agent. The
    design material switches to participants, risk_levels, recipient rows, review
    requests, notices, services, and richer action logs. If an old DB exists, keep
    its tables as legacy_* instead of dropping them.
    """
    legacy_checks = {
        "agents": "name",
        "messages": "from_agent",
        "tasks": "created_by",
        "approvals": "requested_by",
        "action_logs": "actor",
    }
    for table, legacy_col in legacy_checks.items():
        if table_exists(conn, table) and legacy_col in table_columns(conn, table):
            suffix = 1
            target = f"legacy_{table}"
            while table_exists(conn, target):
                suffix += 1
                target = f"legacy_{table}_{suffix}"
            conn.execute(f"ALTER TABLE {table} RENAME TO {target}")


def init_db() -> None:
    with connect() as conn:
        archive_legacy_schema(conn)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                participant_type TEXT NOT NULL,
                role_description TEXT DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS risk_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                sort_order INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                service_type TEXT DEFAULT '',
                url TEXT DEFAULT '',
                host TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL REFERENCES participants(id),
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                risk_level_id INTEGER REFERENCES risk_levels(id),
                status TEXT NOT NULL DEFAULT 'unread',
                requires_approval INTEGER NOT NULL DEFAULT 0,
                approved_by_id INTEGER REFERENCES participants(id),
                approved_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (status IN ('unread','open','pending_approval','delivered','acknowledged','completed','archived'))
            );

            CREATE TABLE IF NOT EXISTS message_recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                recipient_id INTEGER NOT NULL REFERENCES participants(id),
                delivery_status TEXT NOT NULL DEFAULT 'delivered',
                delivered_at TEXT,
                read_at TEXT,
                acknowledged_at TEXT,
                UNIQUE(message_id, recipient_id)
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                created_by_id INTEGER NOT NULL REFERENCES participants(id),
                assigned_to_id INTEGER REFERENCES participants(id),
                risk_level_id INTEGER REFERENCES risk_levels(id),
                status TEXT NOT NULL DEFAULT 'open',
                completion_notes TEXT DEFAULT '',
                blocked_reason TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                CHECK (status IN ('open','in_progress','blocked','completed','archived','cancelled'))
            );

            CREATE TABLE IF NOT EXISTS approval_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requested_by_id INTEGER NOT NULL REFERENCES participants(id),
                requested_for_id INTEGER NOT NULL REFERENCES participants(id),
                target_type TEXT NOT NULL,
                target_id INTEGER,
                action_type TEXT NOT NULL,
                action_summary TEXT NOT NULL,
                proposed_command TEXT DEFAULT '',
                reason TEXT DEFAULT '',
                risk_level_id INTEGER REFERENCES risk_levels(id),
                status TEXT NOT NULL DEFAULT 'pending',
                decided_by_id INTEGER REFERENCES participants(id),
                decision_notes TEXT DEFAULT '',
                requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                decided_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (status IN ('pending','approved','rejected','archived','cancelled'))
            );

            CREATE TABLE IF NOT EXISTS review_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                requested_by_id INTEGER NOT NULL REFERENCES participants(id),
                reviewer_id INTEGER REFERENCES participants(id),
                target_type TEXT NOT NULL,
                target_ref TEXT DEFAULT '',
                risk_level_id INTEGER REFERENCES risk_levels(id),
                status TEXT NOT NULL DEFAULT 'open',
                review_notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                CHECK (status IN ('open','in_progress','completed','archived','cancelled'))
            );

            CREATE TABLE IF NOT EXISTS system_notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER REFERENCES services(id),
                source_participant_id INTEGER REFERENCES participants(id),
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                risk_level_id INTEGER REFERENCES risk_levels(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                resolved_at TEXT,
                CHECK (status IN ('active','acknowledged','resolved','archived'))
            );

            CREATE TABLE IF NOT EXISTS action_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER REFERENCES participants(id),
                action_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                summary TEXT NOT NULL,
                before_json TEXT DEFAULT '',
                after_json TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TRIGGER IF NOT EXISTS participants_updated_at AFTER UPDATE ON participants BEGIN
                UPDATE participants SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
            CREATE TRIGGER IF NOT EXISTS services_updated_at AFTER UPDATE ON services BEGIN
                UPDATE services SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
            CREATE TRIGGER IF NOT EXISTS messages_updated_at AFTER UPDATE ON messages BEGIN
                UPDATE messages SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
            CREATE TRIGGER IF NOT EXISTS tasks_updated_at AFTER UPDATE ON tasks BEGIN
                UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
            CREATE TRIGGER IF NOT EXISTS approvals_updated_at AFTER UPDATE ON approval_requests BEGIN
                UPDATE approval_requests SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
            CREATE TRIGGER IF NOT EXISTS reviews_updated_at AFTER UPDATE ON review_requests BEGIN
                UPDATE review_requests SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
            CREATE TRIGGER IF NOT EXISTS notices_updated_at AFTER UPDATE ON system_notices BEGIN
                UPDATE system_notices SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
            """
        )
        seed_reference_data(conn)
        seed_examples(conn)


def participant_id(conn: sqlite3.Connection, name_or_display: str) -> int:
    value = name_or_display.strip()
    row = conn.execute(
        "SELECT id FROM participants WHERE lower(name)=lower(?) OR lower(display_name)=lower(?)",
        (value, value),
    ).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO participants (name, display_name, participant_type, role_description) VALUES (?, ?, ?, ?)",
        (value.lower().replace(" ", "-"), value, "human", "Added from API input."),
    )
    return int(cur.lastrowid)


def risk_id(conn: sqlite3.Connection, name: str | None) -> int:
    risk_name = name or "UNKNOWN / NEEDS REVIEW"
    row = conn.execute("SELECT id FROM risk_levels WHERE name = ?", (risk_name,)).fetchone()
    if row:
        return int(row["id"])
    fallback = conn.execute("SELECT id FROM risk_levels WHERE name = ?", ("UNKNOWN / NEEDS REVIEW",)).fetchone()
    if fallback:
        return int(fallback["id"])
    cur = conn.execute("INSERT INTO risk_levels (name, description, sort_order) VALUES (?, ?, ?)", (risk_name, "Added from API input.", 999))
    return int(cur.lastrowid)


def service_id(conn: sqlite3.Connection, name: str | None) -> int | None:
    if not name:
        return None
    row = conn.execute("SELECT id FROM services WHERE lower(name)=lower(?)", (name,)).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute("INSERT INTO services (name, service_type) VALUES (?, ?)", (name, "service"))
    return int(cur.lastrowid)


def seed_reference_data(conn: sqlite3.Connection) -> None:
    for name, display, ptype, role in PARTICIPANTS:
        conn.execute(
            "INSERT OR IGNORE INTO participants (name, display_name, participant_type, role_description) VALUES (?, ?, ?, ?)",
            (name, display, ptype, role),
        )
    for idx, (name, description) in enumerate(RISK_LEVELS, start=1):
        conn.execute(
            "INSERT OR IGNORE INTO risk_levels (name, description, sort_order) VALUES (?, ?, ?)",
            (name, description, idx),
        )
    for name, service_type, url, host, notes in SERVICES:
        conn.execute(
            "INSERT OR IGNORE INTO services (name, service_type, url, host, notes) VALUES (?, ?, ?, ?, ?)",
            (name, service_type, url, host, notes),
        )


def count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def log_action(
    conn: sqlite3.Connection,
    actor: str | int,
    action_type: str,
    entity_type: str,
    entity_id: int | None,
    summary: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    actor_id = actor if isinstance(actor, int) else participant_id(conn, actor)
    conn.execute(
        """
        INSERT INTO action_logs (actor_id, action_type, entity_type, entity_id, summary, before_json, after_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            actor_id,
            action_type,
            entity_type,
            entity_id,
            summary,
            json.dumps(before or {}, sort_keys=True),
            json.dumps(after or {}, sort_keys=True),
        ),
    )


def seed_examples(conn: sqlite3.Connection) -> None:
    cameron = participant_id(conn, "Cameron")
    mira = participant_id(conn, "Mira")
    hermes = participant_id(conn, "Hermes")
    nova = participant_id(conn, "Nova")
    nora = participant_id(conn, "Nora")
    kuma = participant_id(conn, "Uptime Kuma")

    if count(conn, "messages") == 0:
        cur = conn.execute(
            """
            INSERT INTO messages (sender_id, subject, body, risk_level_id, status, requires_approval)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                mira,
                "Docker Recovery page updated",
                "I updated the Docker Service Recovery page and aligned the backup paths with the current Backup Strategy layout. Please review the path references and confirm the restore-only warnings are clear.",
                risk_id(conn, "DOCUMENTATION ONLY"),
                "unread",
                0,
            ),
        )
        msg_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO message_recipients (message_id, recipient_id, delivery_status, delivered_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (msg_id, cameron, "delivered"),
        )
        log_action(conn, mira, "create", "message", msg_id, "Seeded documentation review message from Mira to Cameron.")

    if count(conn, "tasks") == 0:
        cur = conn.execute(
            """
            INSERT INTO tasks (title, description, created_by_id, assigned_to_id, risk_level_id, status, completion_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Improve message detail view",
                "Messages can be created, but users need a full detail view with sender, recipients, risk, status, and full body. Add clickable rows or cards that open a detail panel/modal/page.",
                cameron,
                hermes,
                risk_id(conn, "BUILD / UI"),
                "in_progress",
                "Pending final review after UI update.",
            ),
        )
        log_action(conn, cameron, "create", "task", int(cur.lastrowid), "Seeded task: Improve message detail view.")

    if count(conn, "approval_requests") == 0:
        cur = conn.execute(
            """
            INSERT INTO approval_requests (requested_by_id, requested_for_id, target_type, target_id, action_type, action_summary, proposed_command, reason, risk_level_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hermes,
                cameron,
                "service",
                service_id(conn, "BookStack"),
                "service_restart",
                "Restart BookStack after Docker Compose update and verify service health.",
                "cd ~/bookstack && docker compose restart",
                "BookStack is reachable locally but the NPM proxy test failed. A controlled restart may clear the issue.",
                risk_id(conn, "STATE-CHANGING / APPROVAL REQUIRED"),
                "pending",
            ),
        )
        log_action(conn, hermes, "create", "approval", int(cur.lastrowid), "Seeded approval request. No command was executed.")

    if count(conn, "review_requests") == 0:
        cur = conn.execute(
            """
            INSERT INTO review_requests (title, body, requested_by_id, reviewer_id, target_type, target_ref, risk_level_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Review NexusAI UI changes",
                "Please review whether the updated UI matches the operations dashboard, command center, and detail-view wireframes.",
                hermes,
                nova,
                "repo",
                "C:/FilesForNora/NexusAI",
                risk_id(conn, "REVIEW"),
                "open",
            ),
        )
        log_action(conn, hermes, "create", "review", int(cur.lastrowid), "Seeded NexusAI UI review request.")

    if count(conn, "system_notices") == 0:
        cur = conn.execute(
            """
            INSERT INTO system_notices (service_id, source_participant_id, severity, title, body, status, risk_level_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                service_id(conn, "Uptime Kuma"),
                kuma,
                "warning",
                "BookStack response time elevated",
                "Uptime Kuma reported elevated response time. No automated action was taken.",
                "active",
                risk_id(conn, "WARNING"),
            ),
        )
        log_action(conn, nora, "create", "notice", int(cur.lastrowid), "Seeded Uptime Kuma BookStack warning notice.")
