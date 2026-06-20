#!/usr/bin/env python3
"""Scheduled one-shot NexusAI agent worker.

Run once, process at most one approved/unread delivered message for one agent,
optionally create one reply, then exit. This script is safe for Windows Task
Scheduler, cron, or Hermes scheduled jobs because it never loops and never
executes commands from messages.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from typing import Any

from nexusai_client import request

DEFAULT_BASE_URL = "http://127.0.0.1:5055"
DEFAULT_AUTO_REPLY = (
    "Acknowledged. I read your message. NexusAI remains a coordination, "
    "approval, messaging, and audit system only; no commands were executed."
)


def print_json(label: str, value: Any) -> None:
    print(label)
    print(json.dumps(value, indent=2, ensure_ascii=False))


def call(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    """Use the shared NexusAI client helper with env-configured base URL/auth."""
    return request(method, path, payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one bounded NexusAI agent inbox check, then exit.",
        epilog=(
            "Examples:\n"
            "  python scripts/nexusai_agent_worker.py --agent Hermes\n"
            "  python scripts/nexusai_agent_worker.py --agent Hermes --ack --auto-reply\n"
            "  python scripts/nexusai_agent_worker.py --agent Hermes --dry-run\n\n"
            "This script does not loop and does not execute commands."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-url", default=os.getenv("NEXUSAI_URL", DEFAULT_BASE_URL), help="NexusAI base URL")
    parser.add_argument("--agent", required=True, help="Participant name to process, for example Hermes, Mira, or Nova")
    parser.add_argument("--ack", action="store_true", help="Acknowledge the message after marking it read")
    parser.add_argument(
        "--auto-reply",
        nargs="?",
        const=DEFAULT_AUTO_REPLY,
        default="",
        metavar="TEXT",
        help="Create exactly one DOCUMENTATION ONLY reply. Optional TEXT overrides the default reply body.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print intended actions without POSTing read/ack/reply changes")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # nexusai_client.request reads these env vars. Set only for this process.
    os.environ["NEXUSAI_URL"] = args.base_url.rstrip("/")

    print("NexusAI scheduled agent worker")
    print(f"Base URL: {os.environ['NEXUSAI_URL']}")
    print(f"Agent: {args.agent}")
    print(f"Dry run: {'yes' if args.dry_run else 'no'}")
    print("Safety: no command execution; approval does not equal execution.")

    encoded_agent = urllib.parse.quote(args.agent)
    inbox = call("GET", f"/api/agent-inbox/{encoded_agent}?limit=1")
    messages = inbox.get("messages", []) if isinstance(inbox, dict) else []

    if not messages:
        print("No messages")
        return 0

    message = messages[0]
    message_id = message["id"]
    print("Processing one delivered inbox message")
    print(f"Message ID: {message_id}")
    print(f"From: {message.get('from', '')}")
    print(f"Subject: {message.get('subject', '')}")

    if args.dry_run:
        print("DRY RUN: would mark message read")
    else:
        read_result = call("POST", f"/api/messages/{message_id}/read", {"participant": args.agent})
        print_json("Marked read:", read_result)

    if args.ack:
        if args.dry_run:
            print("DRY RUN: would acknowledge message")
        else:
            ack_result = call("POST", f"/api/messages/{message_id}/acknowledge", {"participant": args.agent})
            print_json("Acknowledged:", ack_result)

    if args.auto_reply:
        reply_payload = {
            "from": args.agent,
            "body": args.auto_reply,
            "risk_level": "DOCUMENTATION ONLY",
        }
        if args.dry_run:
            print_json("DRY RUN: would create one reply:", reply_payload)
        else:
            reply = call("POST", f"/api/messages/{message_id}/reply", reply_payload)
            print_json("Created one reply:", reply)
            if isinstance(reply, dict):
                if reply.get("requires_approval") or reply.get("status") == "pending_approval":
                    print("Reply is pending Cameron approval before delivery.")
                else:
                    print("Reply was not held for Cameron approval, likely because recipient is not an AI agent.")

    print("Done. Processed at most one message and exiting.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - scheduled logs need concise failures.
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
