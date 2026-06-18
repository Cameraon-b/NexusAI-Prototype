import os
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


@contextmanager
def client(tmp_path: Path):
    old_db = os.environ.get('NEXUSAI_DB_PATH')
    os.environ['NEXUSAI_DB_PATH'] = str(tmp_path / 'test-nexusai.db')
    try:
        with TestClient(app) as c:
            yield c
    finally:
        if old_db is None:
            os.environ.pop('NEXUSAI_DB_PATH', None)
        else:
            os.environ['NEXUSAI_DB_PATH'] = old_db


def test_agents_seeded(tmp_path):
    with client(tmp_path) as c:
        res = c.get('/api/agents')
        assert res.status_code == 200
        names = [a['name'] for a in res.json()]
        assert names == ['Cameron', 'Nova', 'Mira', 'Hermes', 'OpenClaw', 'System']


def test_create_message_and_logs_action(tmp_path):
    with client(tmp_path) as c:
        payload = {
            'from': 'Mira',
            'to': 'Nova',
            'subject': 'Review Docker Service Recovery page',
            'body': 'Please review path consistency against the current Backup Strategy page.',
            'risk_level': 'DOCUMENTATION ONLY',
            'status': 'open',
        }
        res = c.post('/api/messages', json=payload)
        assert res.status_code == 201
        msg = res.json()
        assert msg['id'] > 0
        assert msg['from'] == 'Mira'
        assert msg['to'] == 'Nova'
        assert msg['risk_level'] == 'DOCUMENTATION ONLY'

        logs = c.get('/api/logs').json()
        assert any(l['action_type'] == 'create' and l['target_type'] == 'message' and l['target_id'] == msg['id'] for l in logs)


def test_create_and_patch_task(tmp_path):
    with client(tmp_path) as c:
        res = c.post('/api/tasks', json={
            'title': 'Draft service registry',
            'description': 'Create a first-pass list of AETHER services.',
            'created_by': 'Hermes',
            'assigned_to': 'Mira',
            'risk_level': 'DOCUMENTATION ONLY',
            'status': 'open',
        })
        assert res.status_code == 201
        task_id = res.json()['id']

        patched = c.patch(f'/api/tasks/{task_id}', json={'status': 'completed', 'completion_notes': 'Draft complete.'})
        assert patched.status_code == 200
        assert patched.json()['status'] == 'completed'
        assert patched.json()['completion_notes'] == 'Draft complete.'


def test_approval_records_but_does_not_execute(tmp_path):
    with client(tmp_path) as c:
        res = c.post('/api/approvals', json={
            'requested_by': 'Hermes',
            'requested_for': 'Cameron',
            'action_summary': 'Restart BookStack Docker Compose service',
            'proposed_command': 'cd /home/noratheredeemer/docker/bookstack && docker compose restart',
            'risk_level': 'STATE-CHANGING / APPROVAL REQUIRED',
            'reason': 'BookStack is unreachable after restore validation.',
            'status': 'pending',
        })
        assert res.status_code == 201
        approval_id = res.json()['id']

        approved = c.patch(f'/api/approvals/{approval_id}', json={'status': 'approved', 'approved_by': 'Cameron'})
        assert approved.status_code == 200
        body = approved.json()
        assert body['status'] == 'approved'
        assert body['approved_by'] == 'Cameron'
        assert body['proposed_command'].startswith('cd /home/noratheredeemer')


def test_invalid_risk_label_rejected(tmp_path):
    with client(tmp_path) as c:
        res = c.post('/api/tasks', json={
            'title': 'Bad task',
            'description': 'This should fail.',
            'created_by': 'Hermes',
            'assigned_to': 'Mira',
            'risk_level': 'LOW',
            'status': 'open',
        })
        assert res.status_code == 422


def test_ui_static_exposes_record_detail_views_and_no_run_buttons(tmp_path):
    with client(tmp_path) as c:
        js = c.get('/static/app.js')
        assert js.status_code == 200
        body = js.text
        assert 'openMessage' in body
        assert 'openTask' in body
        assert 'openApproval' in body
        assert 'Full body' in body
        assert 'Full description' in body
        assert 'Proposed command / action text' in body
        assert 'Copy text' in body
        assert 'Run command' not in body
        assert 'Run service' not in body
