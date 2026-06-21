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
import re
import sys
import urllib.parse
from typing import Any

from nexusai_client import request

DEFAULT_BASE_URL = "http://127.0.0.1:5055"
DEFAULT_AUTO_REPLY = (
    "Acknowledged. I read your message. NexusAI remains a coordination, "
    "approval, messaging, and audit system only; no commands were executed."
)
AUTO_REPLY_MODES = ("ack-only", "template", "agent-bridge")
SAFETY_KEYWORDS = (
    "command",
    "commands",
    "shell",
    "powershell",
    "ssh",
    "docker",
    "compose",
    "deploy",
    "deployment",
    "restart",
    "restore",
    "system change",
    "state-changing",
    "approval",
    "approve",
    "approved",
)


def compact_text(value: Any, max_chars: int = 220) -> str:
    """Normalize message text for short deterministic replies."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def message_discusses_safety_topic(message: dict[str, Any]) -> bool:
    """Return true when a contextual reply should include the short safety line."""
    haystack = f"{message.get('subject', '')} {message.get('body', '')}".lower()
    return any(keyword in haystack for keyword in SAFETY_KEYWORDS)


def build_template_reply(message: dict[str, Any]) -> str:
    """Build a short contextual reply without calling tools or claiming work."""
    subject = compact_text(message.get("subject") or "No subject", 120)
    body = compact_text(message.get("body") or "the message", 220)
    body_fragment = re.sub(r"[.!?]+", ",", body).strip(" ,") or "the message"

    sentences = [
        f"Subject: {subject}.",
        f"I read your note: \"{body_fragment}\".",
        "My answer is to keep the next step scoped to the message topic and turn it into a clear NexusAI task or reply without claiming any work has already been performed.",
        "Next checklist item: identify the owner, desired outcome, and any approval gate before moving this forward.",
    ]
    if message_discusses_safety_topic(message):
        sentences.append("Safety: approval records permission only; it is not execution and does not execute commands or apply system changes.")
    return " ".join(sentences)


def build_auto_reply_body(message: dict[str, Any], mode: str, explicit_text: str = "") -> str:
    """Return the reply body for the selected auto-reply mode."""
    if mode == "ack-only":
        return explicit_text or DEFAULT_AUTO_REPLY
    if mode == "template":
        if explicit_text:
            return explicit_text
        return build_template_reply(message)
    if mode == "agent-bridge":
        raise NotImplementedError(
            "agent-bridge auto-reply mode is a placeholder for a future real agent/runtime bridge; "
            "it does not execute commands or create a generated reply yet."
        )
    raise ValueError(f"Unsupported auto-reply mode: {mode}")


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
        help=(
            "Create exactly one DOCUMENTATION ONLY reply. Optional TEXT overrides the generated body "
            "for ack-only/template modes."
        ),
    )
    parser.add_argument(
        "--auto-reply-mode",
        choices=AUTO_REPLY_MODES,
        default="ack-only",
        help="Auto-reply behavior: ack-only keeps the generic acknowledgement; template builds a short contextual reply; agent-bridge is a future placeholder.",
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
    print(f"Auto-reply mode: {args.auto_reply_mode}")
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
        explicit_reply_text = "" if args.auto_reply == DEFAULT_AUTO_REPLY else args.auto_reply
        try:
            reply_body = build_auto_reply_body(message, args.auto_reply_mode, explicit_reply_text)
        except NotImplementedError as exc:
            print(f"Auto-reply skipped: {exc}")
            print("Done. Processed at most one message and exiting.")
            return 0

        reply_payload = {
            "from": args.agent,
            "body": reply_body,
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
