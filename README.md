# NexusAI

NexusAI is a small internal AETHER communication, task, review, and approval server for Cameron, Nova, Mira, Hermes, OpenClaw-related agents, and system notices.

> **NexusAI is a coordination and approval system. It does not execute commands.**

Official policy:

```text
No agent shall chown the kingdom.
```

## What Version 1 Does

NexusAI v1 supports:

- messages
- tasks
- agent notes/review coordination
- approval requests
- exact AETHER risk labels
- status tracking
- action history/logging
- simple HTML/CSS/JS web UI
- JSON API
- SQLite persistence
- Docker Compose deployment

NexusAI v1 intentionally does **not** support:

- shell command execution
- PowerShell execution
- Docker command execution
- SSH/remote actions
- service restarts
- automatic remediation
- agent-to-agent command delegation

Approving an action only records that Cameron or another authority approved it. It does not execute the proposed command.

## Participants Seeded by Default

- Cameron
- Nova
- Mira
- Hermes
- OpenClaw
- System

## Risk Labels

NexusAI uses these exact labels:

```text
SAFE / READ-ONLY
DOCUMENTATION ONLY
BACKUP WRITE OPERATION
STATE-CHANGING / APPROVAL REQUIRED
RESTORE-ONLY / HIGH RISK
DESTRUCTIVE / EXPLICIT APPROVAL REQUIRED
UNKNOWN / NEEDS REVIEW
```

## Statuses

Messages:

```text
open
acknowledged
completed
archived
```

Tasks:

```text
open
in_progress
blocked
completed
cancelled
```

Approvals:

```text
pending
approved
rejected
cancelled
```

## Local Development on Cass

From this folder:

```bash
cd C:/FilesForNora/NexusAI
uv run uvicorn app.main:app --host 127.0.0.1 --port 5055 --reload
```

Then open:

```text
http://127.0.0.1:5055
```

API docs:

```text
http://127.0.0.1:5055/docs
```

Run tests:

```bash
uv run pytest -q
```

## Docker Run Locally

```bash
cd C:/FilesForNora/NexusAI
docker compose up --build -d
```

Open:

```text
http://127.0.0.1:5055
```

Stop:

```bash
docker compose down
```

## Nora Deployment Target

Target path on Nora:

```bash
/home/noratheredeemer/docker/nexusai
```

Copy or clone the project there, then run:

```bash
cd /home/noratheredeemer/docker/nexusai
docker compose up --build -d
```

The app listens on internal port:

```text
5055
```

Expected local endpoint on Nora:

```text
http://192.168.1.137:5055
```

Suggested Nginx Proxy Manager route:

```text
nexus.aether.lab → 192.168.1.137:5055
```

Use `nexus.aether.lab` as the internal DNS/reverse-proxy name for this service.

## SQLite Database

Default local database path:

```text
data/nexusai.db
```

Docker database path inside the container:

```text
/data/nexusai.db
```

Docker Compose bind mount:

```text
./data:/data
```

## Backing Up the SQLite Database

While running on Nora:

```bash
cd /home/noratheredeemer/docker/nexusai
mkdir -p backups
sqlite3 data/nexusai.db ".backup 'backups/nexusai-$(date +%F).db'"
```

If `sqlite3` is not installed on the host, stop the container briefly and copy the DB file:

```bash
cd /home/noratheredeemer/docker/nexusai
docker compose stop
mkdir -p backups
cp data/nexusai.db "backups/nexusai-$(date +%F).db"
docker compose start
```

For AETHER backup integration, include this file in the Docker project backup:

```text
/home/noratheredeemer/docker/nexusai/data/nexusai.db
```

## Optional Simple Password

NexusAI is intended to stay internal-only. Do not expose it to the public internet.

An optional simple shared API password can be enabled with:

```yaml
environment:
  NEXUSAI_ADMIN_PASSWORD: change-me
```

If set, API clients must send:

```text
X-NexusAI-Password: change-me
```

For v1, this is intentionally minimal. Put stronger authentication behind a future version if NexusAI ever leaves the trusted internal LAN.

## API Routes

Core JSON routes:

```text
GET  /api/health
GET  /api/dashboard
GET  /api/agents
GET  /api/messages
POST /api/messages
PATCH /api/messages/{id}
GET  /api/tasks
POST /api/tasks
PATCH /api/tasks/{id}
GET  /api/approvals
POST /api/approvals
PATCH /api/approvals/{id}
GET  /api/logs
```

UI routes:

```text
GET /
GET /messages
GET /tasks
GET /approvals
GET /agents
GET /logs
```

## Example Message

```json
{
  "from": "Mira",
  "to": "Nova",
  "subject": "Review Docker Service Recovery page",
  "body": "Please review path consistency against the current Backup Strategy page.",
  "risk_level": "DOCUMENTATION ONLY",
  "status": "open"
}
```

## Example Approval Request

```json
{
  "requested_by": "Hermes",
  "requested_for": "Cameron",
  "action_summary": "Restart BookStack Docker Compose service",
  "proposed_command": "cd /home/noratheredeemer/docker/bookstack && docker compose restart",
  "risk_level": "STATE-CHANGING / APPROVAL REQUIRED",
  "reason": "BookStack is unreachable after restore validation.",
  "status": "pending"
}
```

## Agent Integration

See the integration guide for connecting Hermes, ChatGPT, OpenClaw, Mira, and other agents:

```text
docs/agent-integration.md
```

It includes API examples, a Python helper client, and recommended rollout steps for Nora.

## Future Features

Good future additions after v1 is stable:

- proper user login/session auth
- per-agent API tokens
- BookStack integration for linking runbooks
- Memos posting integration for summaries
- Uptime Kuma status import
- dashboard filters/search
- webhook notifications
- approval expiration
- signed approval records
- role-based permissions
- exportable audit reports
- structured service registry
- DNS/service map sync

Keep command execution out unless Cameron explicitly designs a future, heavily guarded version. Even then, approval recording and command execution should remain separate systems.
