#!/usr/bin/env python3
"""Tiny NexusAI client for agents/scripts.

Usage examples:
  python scripts/nexusai_client.py message --from Hermes --to Cameron --subject "Hello" --body "NexusAI is reachable."
  python scripts/nexusai_client.py task --created-by Cameron --assigned-to Hermes --title "Check BookStack" --description "Review status only."
  python scripts/nexusai_client.py approval --requested-by Hermes --requested-for Cameron --summary "Restart service" --proposed-command "docker compose restart" --reason "Service unreachable"
  python scripts/nexusai_client.py inbox --agent Hermes

Environment:
  NEXUSAI_URL defaults to http://127.0.0.1:5055
  NEXUSAI_PASSWORD is sent as X-NexusAI-Password when set
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_RISK = "UNKNOWN / NEEDS REVIEW"


def request(method: str, path: str, payload: dict | None = None) -> object:
    base_url = os.getenv("NEXUSAI_URL", "http://127.0.0.1:5055").rstrip("/")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{base_url}{path}", data=data, method=method)
    req.add_header("Accept", "application/json")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    password = os.getenv("NEXUSAI_PASSWORD", "")
    if password:
        req.add_header("X-NexusAI-Password", password)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"NexusAI HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Could not reach NexusAI: {exc.reason}") from exc


def print_json(obj: object) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Post/read NexusAI messages, tasks, and approvals.")
    sub = parser.add_subparsers(dest="command", required=True)

    health = sub.add_parser("health", help="Check NexusAI health")

    inbox = sub.add_parser("inbox", help="Show open dashboard items, optionally filtered for an agent")
    inbox.add_argument("--agent", default="", help="Agent name to filter messages/tasks/approvals")

    msg = sub.add_parser("message", help="Create a NexusAI message")
    msg.add_argument("--from", dest="from_agent", required=True)
    msg.add_argument("--to", required=True)
    msg.add_argument("--subject", required=True)
    msg.add_argument("--body", required=True)
    msg.add_argument("--risk-level", default=DEFAULT_RISK)
    msg.add_argument("--status", default="open")

    task = sub.add_parser("task", help="Create a NexusAI task")
    task.add_argument("--created-by", required=True)
    task.add_argument("--assigned-to", required=True)
    task.add_argument("--title", required=True)
    task.add_argument("--description", required=True)
    task.add_argument("--risk-level", default=DEFAULT_RISK)
    task.add_argument("--status", default="open")

    approval = sub.add_parser("approval", help="Create an inert approval request")
    approval.add_argument("--requested-by", required=True)
    approval.add_argument("--requested-for", required=True)
    approval.add_argument("--summary", required=True)
    approval.add_argument("--proposed-command", default="")
    approval.add_argument("--reason", required=True)
    approval.add_argument("--risk-level", default="STATE-CHANGING / APPROVAL REQUIRED")
    approval.add_argument("--status", default="pending")

    args = parser.parse_args(argv)

    if args.command == "health":
        print_json(request("GET", "/api/health"))
        return 0

    if args.command == "inbox":
        dashboard = request("GET", "/api/dashboard")
        if args.agent and isinstance(dashboard, dict):
            agent = args.agent.lower()
            dashboard = {
                "open_messages": [m for m in dashboard.get("open_messages", []) if str(m.get("to", "")).lower() == agent or str(m.get("from", "")).lower() == agent],
                "open_tasks": [t for t in dashboard.get("open_tasks", []) if str(t.get("assigned_to", "")).lower() == agent or str(t.get("created_by", "")).lower() == agent],
                "pending_approvals": [a for a in dashboard.get("pending_approvals", []) if str(a.get("requested_for", "")).lower() == agent or str(a.get("requested_by", "")).lower() == agent],
            }
        print_json(dashboard)
        return 0

    if args.command == "message":
        print_json(request("POST", "/api/messages", {
            "from": args.from_agent,
            "to": args.to,
            "subject": args.subject,
            "body": args.body,
            "risk_level": args.risk_level,
            "status": args.status,
        }))
        return 0

    if args.command == "task":
        print_json(request("POST", "/api/tasks", {
            "created_by": args.created_by,
            "assigned_to": args.assigned_to,
            "title": args.title,
            "description": args.description,
            "risk_level": args.risk_level,
            "status": args.status,
        }))
        return 0

    if args.command == "approval":
        print_json(request("POST", "/api/approvals", {
            "requested_by": args.requested_by,
            "requested_for": args.requested_for,
            "action_summary": args.summary,
            "proposed_command": args.proposed_command,
            "risk_level": args.risk_level,
            "reason": args.reason,
            "status": args.status,
        }))
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
