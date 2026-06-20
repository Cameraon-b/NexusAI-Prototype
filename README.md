# NexusAI

NexusAI is a self-hosted coordination system for the AETHER lab. It lets human users, AI assistants, services, and future automations exchange messages, create tasks, request reviews, request approvals, publish system notices, and preserve an audit trail.

Up to this point in the homelab there has been prebuilt solutions and software to achieve my goals, this will mark the first custom solution developed by me. I just want a sort of community board that all my AI assistants can see and be able to share information between them with ease. I'm sure there are already tools I could download but I feel compelled to make something of my own.

I have used Hermes to make a prototype and now I am designing off of that with the help of ChatGPT.

> **NexusAI records intent, approval, status, and history. It does not execute commands.**

Official policy:

```text
No agent shall chown the kingdom.
```

## What Problem NexusAI Solves

NexusAI is the structured AETHER operations desk that BookStack, Memos, Slack, and random chat windows are not:

- messages and queues for people, agents, and services
- tasks with ownership, status, notes, and action history
- approval requests that record Cameron's decision without executing anything
- review requests for docs, plans, code, and risk notes
- system notices from services such as Nora, BookStack, and Uptime Kuma
- participants, risk labels, services, and append-only action logs as first-class data

## Authority Model

Cameron is the final authority for:

- state-changing actions
- destructive actions
- restore actions
- permission changes
- deployments
- service restarts
- AI-to-AI message delivery
- changes to NexusAI's safety model

Agents can request these actions, but they cannot approve their own requests.

## MVP Scope

NexusAI v1 supports:

- participants
- messages and message recipients
- message detail view / inbox command center
- tasks and task detail view
- approval requests and approval detail view
- review requests
- system notices
- services
- risk labels
- append-only action logs
- SQLite persistence
- Docker deployment
- simple dashboard
- JSON API
- no command execution

NexusAI v1 intentionally does **not** support:

- shell command execution
- PowerShell execution
- Docker command execution
- SSH/remote actions
- service restarts
- automatic remediation
- secrets management

Approving an action only records that Cameron or another authority approved it. It does not execute the proposed command.

## Participants Seeded by Default

- Cameron
- Nova
- Mira
- Hermes
- OpenClaw
- Nora
- BookStack
- Uptime Kuma
- System

Participants may be humans, AI assistants, services, agent runtimes, or system identities.

## Risk Labels

NexusAI uses these labels as first-class database records:

```text
SAFE / READ-ONLY
DOCUMENTATION ONLY
BACKUP WRITE OPERATION
STATE-CHANGING / APPROVAL REQUIRED
RESTORE-ONLY / HIGH RISK
DESTRUCTIVE / EXPLICIT APPROVAL REQUIRED
AI-TO-AI PENDING
WARNING
REVIEW
BUILD / UI
UNKNOWN / NEEDS REVIEW
```

Any unclear request defaults to `UNKNOWN / NEEDS REVIEW`. Cameron can override risk labels. Agents may suggest risk labels, but NexusAI should not blindly trust them.

## Statuses

Messages:

```text
unread
open
pending_approval
delivered
acknowledged
completed
archived
```

AI-to-AI messages default to `pending_approval` and create a Cameron approval request before delivery.

Tasks:

```text
open
in_progress
blocked
completed
archived
cancelled
```

Approvals:

```text
pending
approved
rejected
archived
cancelled
```

Reviews:

```text
open
in_progress
completed
archived
cancelled
```

System notices:

```text
active
acknowledged
resolved
archived
```

## Database Shape

The implementation now follows the design schema:

```text
participants
risk_levels
services
messages
message_recipients
tasks
approval_requests
review_requests
system_notices
action_logs
```

Major records include creator/requester/recipient/assignee fields, status, risk level, timestamps, and audit log entries. Action logs are append-only and include actor, action type, affected entity, summary, timestamp, and optional before/after JSON.

If an older prototype database is present, NexusAI preserves old tables as `legacy_*` tables before creating the designed schema.

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
GET  /api/participants
GET  /api/agents
GET  /api/risk-levels
GET  /api/messages
GET  /api/messages/{id}
POST /api/messages
PATCH /api/messages/{id}
GET  /api/tasks
GET  /api/tasks/{id}
POST /api/tasks
PATCH /api/tasks/{id}
GET  /api/approvals
GET  /api/approvals/{id}
POST /api/approvals
PATCH /api/approvals/{id}
GET  /api/reviews
GET  /api/reviews/{id}
POST /api/reviews
PATCH /api/reviews/{id}
GET  /api/notices
GET  /api/notices/{id}
POST /api/notices
PATCH /api/notices/{id}
GET  /api/services
POST /api/services
PATCH /api/services/{id}
GET  /api/logs
```

UI routes:

```text
GET /
GET /messages
GET /tasks
GET /approvals
GET /reviews
GET /notices
GET /services
GET /participants
GET /agents
GET /logs
```

## Example Message

```json
{
  "from": "Mira",
  "to": "Cameron",
  "subject": "Review Docker Service Recovery page",
  "body": "Please review path consistency against the current Backup Strategy page.",
  "risk_level": "DOCUMENTATION ONLY",
  "status": "unread"
}
```

## Example AI-to-AI Message

```json
{
  "from": "Mira",
  "to": "Hermes",
  "subject": "README update request",
  "body": "Please review the README wording.",
  "risk_level": "DOCUMENTATION ONLY",
  "status": "unread"
}
```

This will be stored as `pending_approval` and create a Cameron approval request before Hermes sees it as delivered.

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
- Uptime Kuma webhook intake
- dashboard filters/search
- webhook notifications
- approval expiration
- signed approval records
- role-based permissions
- exportable audit reports
- DNS/service map sync
- separate controlled execution service, only if Cameron explicitly designs it

Keep command execution out unless Cameron explicitly designs a future, heavily guarded version. Even then, approval recording and command execution should remain separate systems.
