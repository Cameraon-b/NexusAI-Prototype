#!/usr/bin/env python3
"""Poll one NexusAI agent inbox once.

This helper is intentionally bounded: one check, at most one message, optional
one reply, then exit. Schedule it every 5-10 minutes via cron/Hermes/Task
Scheduler rather than running a tight loop.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, password: str | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if password:
        headers["X-NexusAI-Password"] = password
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code}: {body}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll one NexusAI agent inbox once.")
    parser.add_argument("--base-url", default=os.getenv("NEXUSAI_BASE_URL", "http://127.0.0.1:5055"))
    parser.add_argument("--agent", required=True, help="Participant name, for example Hermes, Mira, or Nova")
    parser.add_argument("--password", default=os.getenv("NEXUSAI_ADMIN_PASSWORD", ""))
    parser.add_argument("--reply", default="", help="Optional one-shot reply body. If omitted, no reply is created.")
    parser.add_argument("--ack", action="store_true", help="Acknowledge after reading instead of only marking read.")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    agent = urllib.parse.quote(args.agent)
    password = args.password or None

    inbox = request_json("GET", f"{base}/api/agent-inbox/{agent}?limit=1", password=password)
    messages = inbox.get("messages", [])
    if not messages:
        return 0

    message = messages[0]
    message_id = message["id"]
    print(json.dumps({
        "received": True,
        "agent": args.agent,
        "message_id": message_id,
        "conversation_id": message.get("conversation_id"),
        "parent_message_id": message.get("parent_message_id"),
        "from": message.get("from"),
        "subject": message.get("subject"),
        "body": message.get("body"),
    }, indent=2))

    request_json("POST", f"{base}/api/messages/{message_id}/read", {"participant": args.agent}, password=password)

    if args.ack:
        request_json("POST", f"{base}/api/messages/{message_id}/acknowledge", {"participant": args.agent}, password=password)

    if args.reply:
        reply = request_json("POST", f"{base}/api/messages/{message_id}/reply", {
            "from": args.agent,
            "body": args.reply,
            "risk_level": "DOCUMENTATION ONLY",
        }, password=password)
        print(json.dumps({
            "reply_created": True,
            "reply_id": reply.get("id"),
            "conversation_id": reply.get("conversation_id"),
            "parent_message_id": reply.get("parent_message_id"),
            "status": reply.get("status"),
            "delivery_status": reply.get("delivery_status"),
            "requires_approval": reply.get("requires_approval"),
        }, indent=2))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI should emit concise failures.
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
