from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def read_script(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def assert_bridge_cycle_script(content: str, agent: str, log_name: str) -> None:
    assert '$Project = "C:\\FilesForNora\\NexusAI"' in content
    assert '$BridgeDir = "$Project\\scripts\\bridge_queue"' in content
    assert f'$Log = "$LogDir\\{log_name}"' in content
    assert 'New-Item -ItemType Directory -Force -Path $LogDir | Out-Null' in content
    assert 'New-Item -ItemType Directory -Force -Path $BridgeDir | Out-Null' in content
    assert 'Set-Location $Project' in content
    assert f'=== {agent} bridge cycle $(Get-Date) ===' in content
    assert '--- Step 1: Worker create/request or consume existing response ---' in content
    assert '--- Step 2: Bridge responder generate response ---' in content
    assert '--- Step 3: Worker post response ---' in content
    assert content.count('nexusai_agent_worker.py') == 2
    assert content.count('nexusai_bridge_responder.py') == 1
    assert '--base-url "http://nexus.aether.lab"' in content
    assert f'--agent "{agent}"' in content
    assert '--auto-reply-mode "bridge-file"' in content
    assert '--bridge-fallback "none"' in content
    assert '--mode "template"' in content
    assert 'Out-File -FilePath $Log -Append' in content
    assert 'docker' not in content.lower()
    assert 'ssh' not in content.lower()


def test_hermes_bridge_cycle_script_exists_and_runs_three_logged_steps():
    assert_bridge_cycle_script(read_script("run-hermes-bridge-cycle.ps1"), "Hermes", "hermes-bridge-cycle.log")


def test_mira_bridge_cycle_script_exists_and_runs_three_logged_steps():
    assert_bridge_cycle_script(read_script("run-mira-bridge-cycle.ps1"), "Mira", "mira-bridge-cycle.log")


def test_existing_template_poller_scripts_are_still_present():
    assert (SCRIPTS / "run-hermes-poller.ps1").exists()
    assert (SCRIPTS / "run-mira-poller.ps1").exists()
