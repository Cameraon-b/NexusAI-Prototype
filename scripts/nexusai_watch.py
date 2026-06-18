#!/usr/bin/env python3
"""Poll NexusAI for new items assigned to an agent.

This script only reads NexusAI and prints notifications. It does not execute
commands, apply approvals, restart services, or remediate anything.

Examples:
  python scripts/nexusai_watch.py --agent Hermes --once
  python scripts/nexusai_watch.py --agent Mira --interval 60

Environment:
  NEXUSAI_URL defaults to http://127.0.0.1:5055
  NEXUSAI_PASSWORD is sent as X-NexusAI-Password when set
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def request_json(path: str) -> Any:
    base_url = os.getenv("NEXUSAI_URL", "http://127.0.0.1:5055").rstrip("/")
    req = urllib.request.Request(f"{base_url}{path}", method="GET")
    req.add_header("Accept", "application/json")
    password = os.getenv("NEXUSAI_PASSWORD", "")
    if password:
        req.add_header("X-NexusAI-Password", password)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"NexusAI HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Could not reach NexusAI: {exc.reason}") from exc


def default_state_path(agent: str) -> Path:
    safe_agent = "".join(ch.lower() if ch.isalnum() else "-" for ch in agent).strip("-") or "agent"
    return Path("data") / f"nexusai-seen-{safe_agent}.json"


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_seen(path: Path, seen: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(seen), indent=2), encoding="utf-8")


def collect_items(agent: str) -> list[dict[str, str]]:
    agent_lower = agent.lower()
    dashboard = request_json("/api/dashboard")
    found: list[dict[str, str]] = []

    for item in dashboard.get("open_messages", []):
        if str(item.get("to", "")).lower() == agent_lower:
            found.append({
                "key": f"message:{item['id']}",
                "kind": "message",
                "id": str(item["id"]),
                "title": item.get("subject", ""),
                "from": item.get("from", ""),
                "risk": item.get("risk_level", ""),
            })

    for item in dashboard.get("open_tasks", []):
        if str(item.get("assigned_to", "")).lower() == agent_lower:
            found.append({
                "key": f"task:{item['id']}",
                "kind": "task",
                "id": str(item["id"]),
                "title": item.get("title", ""),
                "from": item.get("created_by", ""),
                "risk": item.get("risk_level", ""),
            })

    for item in dashboard.get("pending_approvals", []):
        if str(item.get("requested_for", "")).lower() == agent_lower:
            found.append({
                "key": f"approval:{item['id']}",
                "kind": "approval",
                "id": str(item["id"]),
                "title": item.get("action_summary", ""),
                "from": item.get("requested_by", ""),
                "risk": item.get("risk_level", ""),
            })

    return found


def print_notifications(items: list[dict[str, str]]) -> None:
    for item in items:
        print(
            f"NexusAI new {item['kind']} #{item['id']} for this agent: "
            f"{item['title']} | from={item['from']} | risk={item['risk']}"
        )


def tick(agent: str, state_path: Path, mark_existing: bool = False) -> int:
    seen = load_seen(state_path)
    items = collect_items(agent)
    if mark_existing and not seen:
        save_seen(state_path, {item["key"] for item in items})
        return 0
    new_items = [item for item in items if item["key"] not in seen]
    if new_items:
        print_notifications(new_items)
        seen.update(item["key"] for item in new_items)
        save_seen(state_path, seen)
    return len(new_items)


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll NexusAI for new items assigned to an agent.")
    parser.add_argument("--agent", default=os.getenv("NEXUSAI_AGENT", "Hermes"))
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--interval", type=int, default=0, help="Poll every N seconds. 0 means run once.")
    parser.add_argument("--once", action="store_true", help="Run once, then exit.")
    parser.add_argument("--mark-existing", action="store_true", help="Record current items as seen without printing them.")
    args = parser.parse_args()

    state_path = args.state or default_state_path(args.agent)

    if args.once or args.interval <= 0:
        return 0 if tick(args.agent, state_path, args.mark_existing) >= 0 else 1

    if args.mark_existing:
        tick(args.agent, state_path, True)
    while True:
        tick(args.agent, state_path, False)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
