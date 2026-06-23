import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import nexusai_agent_worker as worker  # noqa: E402


def test_auto_reply_mode_defaults_to_ack_only():
    args = worker.build_parser().parse_args(["--agent", "Hermes"])

    assert args.auto_reply_mode == "ack-only"


def test_auto_reply_mode_accepts_template_and_rejects_unknown():
    parser = worker.build_parser()

    args = parser.parse_args(["--agent", "Hermes", "--auto-reply", "--auto-reply-mode", "template"])

    assert args.auto_reply_mode == "template"
    with pytest.raises(SystemExit):
        parser.parse_args(["--agent", "Hermes", "--auto-reply-mode", "execute"])


def test_ack_only_reply_matches_existing_safe_generic_ack():
    message = {
        "subject": "Deployment checklist",
        "body": "Please review the deployment checklist only.",
    }

    body = worker.build_auto_reply_body(message, "ack-only")

    assert body == worker.DEFAULT_AUTO_REPLY


def test_template_reply_is_contextual_and_omits_irrelevant_safety_statement():
    message = {
        "subject": "Task board setup",
        "body": "Can you help shape how Hermes and Mira should exchange task updates in NexusAI?",
    }

    body = worker.build_auto_reply_body(message, "template")

    assert "Task board setup" in body
    assert "task" in body.lower()
    assert "NexusAI remains a coordination" not in body
    assert "Next" in body or "Question" in body or "Checklist" in body
    sentence_count = sum(body.count(p) for p in ".?!")
    assert 2 <= sentence_count <= 5


def test_template_reply_adds_safety_line_only_for_system_change_topics():
    message = {
        "subject": "BookStack deployment approval",
        "body": "Should we run docker compose restart after Cameron approves the deployment?",
    }

    body = worker.build_auto_reply_body(message, "template")

    assert "BookStack deployment approval" in body
    assert "approval" in body.lower()
    assert "execution" in body.lower() or "executed" in body.lower()


def test_agent_bridge_mode_aliases_bridge_file_and_does_not_generate_immediate_body():
    parser = worker.build_parser()
    args = parser.parse_args(["--agent", "Hermes", "--auto-reply", "--auto-reply-mode", "bridge-file", "--bridge-fallback", "none"])
    assert args.auto_reply_mode == "bridge-file"
    message = {"subject": "Future bridge", "body": "Please hand this to the real runtime later."}
    with pytest.raises(ValueError):
        worker.build_auto_reply_body(message, "bridge-file")


def test_bridge_file_first_run_creates_request_without_read_or_ack(tmp_path, monkeypatch):
    bridge_dir = tmp_path / "bridge"
    message = {
        "id": 42,
        "conversation_id": 7,
        "from": "Mira",
        "to": "Hermes",
        "subject": "Bridge ordering",
        "body": "Please bridge this safely.",
        "risk_level": worker.DEFAULT_RISK,
        "status": "delivered",
        "delivery_status": "delivered",
    }
    calls = []

    def fake_call(method, path, payload=None):
        calls.append((method, path, payload))
        if path.startswith("/api/agent-inbox/"):
            return {"messages": [message]}
        if path == "/api/conversations/7/messages":
            return []
        raise AssertionError(f"unexpected call: {method} {path} {payload}")

    monkeypatch.setattr(worker, "call", fake_call)

    code = worker.main([
        "--base-url", "http://example.test",
        "--agent", "Hermes",
        "--ack",
        "--auto-reply",
        "--auto-reply-mode", "bridge-file",
        "--bridge-dir", str(bridge_dir),
        "--bridge-fallback", "none",
    ])

    assert code == 0
    assert (bridge_dir / "request-message-42-Hermes.json").exists()
    paths = [path for _method, path, _payload in calls]
    assert "/api/messages/42/read" not in paths
    assert "/api/messages/42/acknowledge" not in paths
    assert "/api/messages/42/reply" not in paths


def test_bridge_file_response_posts_after_acknowledged_parent_without_duplicate(tmp_path, monkeypatch):
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir()
    request_path = bridge_dir / "request-message-42-Hermes.json"
    response_path = bridge_dir / "response-message-42-Hermes.json"
    request_path.write_text("{}\n", encoding="utf-8")
    response_path.write_text(
        '{"message_id": 42, "agent": "Hermes", "reply_body": "Bridge response ready.", "risk_level": "DOCUMENTATION ONLY", "ready": true}\n',
        encoding="utf-8",
    )
    parent = {
        "id": 42,
        "conversation_id": 7,
        "from": "Mira",
        "to": "Hermes",
        "subject": "Bridge ordering",
        "body": "Please bridge this safely.",
        "risk_level": worker.DEFAULT_RISK,
        "status": "acknowledged",
        "delivery_status": "acknowledged",
        "requires_approval": True,
        "approved_by": "Cameron",
    }
    calls = []

    def fake_call(method, path, payload=None):
        calls.append((method, path, payload))
        if method == "GET" and path == "/api/messages/42":
            return parent
        if method == "GET" and path == "/api/conversations/7/messages":
            return [parent]
        if method == "POST" and path == "/api/messages/42/reply":
            return {
                "id": 99,
                "parent_message_id": 42,
                "from": "Hermes",
                "to": "Mira",
                "status": "pending_approval",
                "delivery_status": "pending_approval",
                "requires_approval": True,
            }
        raise AssertionError(f"unexpected call: {method} {path} {payload}")

    monkeypatch.setattr(worker, "call", fake_call)

    code = worker.main([
        "--base-url", "http://example.test",
        "--agent", "Hermes",
        "--ack",
        "--auto-reply",
        "--auto-reply-mode", "bridge-file",
        "--bridge-dir", str(bridge_dir),
        "--bridge-fallback", "none",
    ])

    assert code == 0
    assert not response_path.exists()
    assert list((bridge_dir / "archive").glob("response-message-42-Hermes-processed-*.json"))
    reply_calls = [c for c in calls if c[1] == "/api/messages/42/reply"]
    assert len(reply_calls) == 1
    assert reply_calls[0][2]["body"] == "Bridge response ready."
    paths = [path for _method, path, _payload in calls]
    assert "/api/messages/42/read" not in paths
    assert "/api/messages/42/acknowledge" not in paths


def test_bridge_file_duplicate_response_is_archived_without_second_reply(tmp_path, monkeypatch):
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir()
    (bridge_dir / "request-message-42-Hermes.json").write_text("{}\n", encoding="utf-8")
    response_path = bridge_dir / "response-message-42-Hermes.json"
    response_path.write_text(
        '{"message_id": 42, "agent": "Hermes", "reply_body": "Bridge response ready again.", "risk_level": "DOCUMENTATION ONLY", "ready": true}\n',
        encoding="utf-8",
    )
    parent = {"id": 42, "conversation_id": 7, "from": "Mira", "to": "Hermes", "status": "acknowledged", "delivery_status": "acknowledged"}
    existing_reply = {"id": 99, "parent_message_id": 42, "from": "Hermes", "to": "Mira", "status": "pending_approval"}
    calls = []

    def fake_call(method, path, payload=None):
        calls.append((method, path, payload))
        if method == "GET" and path == "/api/messages/42":
            return parent
        if method == "GET" and path == "/api/conversations/7/messages":
            return [parent, existing_reply]
        raise AssertionError(f"unexpected call: {method} {path} {payload}")

    monkeypatch.setattr(worker, "call", fake_call)
    code = worker.main([
        "--agent", "Hermes",
        "--ack",
        "--auto-reply",
        "--auto-reply-mode", "bridge-file",
        "--bridge-dir", str(bridge_dir),
    ])

    assert code == 0
    assert not response_path.exists()
    assert all(path != "/api/messages/42/reply" for _method, path, _payload in calls)
