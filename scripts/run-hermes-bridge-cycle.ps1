$Project = "C:\FilesForNora\NexusAI"
$LogDir = "$Project\logs"
$BridgeDir = "$Project\scripts\bridge_queue"
$Log = "$LogDir\hermes-bridge-cycle.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $BridgeDir | Out-Null

Set-Location $Project

"`n=== Hermes bridge cycle $(Get-Date) ===" | Out-File -FilePath $Log -Append
"Project: $Project" | Out-File -FilePath $Log -Append
"BridgeDir: $BridgeDir" | Out-File -FilePath $Log -Append

"--- Step 1: Worker create/request or consume existing response ---" | Out-File -FilePath $Log -Append
py "$Project\scripts\nexusai_agent_worker.py" `
  --base-url "http://nexus.aether.lab" `
  --agent "Hermes" `
  --ack `
  --auto-reply `
  --auto-reply-mode "bridge-file" `
  --bridge-fallback "none" 2>&1 | Out-File -FilePath $Log -Append
"Step 1 exit code: $LASTEXITCODE" | Out-File -FilePath $Log -Append

"--- Step 2: Bridge responder generate response ---" | Out-File -FilePath $Log -Append
py "$Project\scripts\nexusai_bridge_responder.py" `
  --agent "Hermes" `
  --bridge-dir "$BridgeDir" `
  --mode "template" 2>&1 | Out-File -FilePath $Log -Append
"Step 2 exit code: $LASTEXITCODE" | Out-File -FilePath $Log -Append

"--- Step 3: Worker post response ---" | Out-File -FilePath $Log -Append
py "$Project\scripts\nexusai_agent_worker.py" `
  --base-url "http://nexus.aether.lab" `
  --agent "Hermes" `
  --ack `
  --auto-reply `
  --auto-reply-mode "bridge-file" `
  --bridge-fallback "none" 2>&1 | Out-File -FilePath $Log -Append
"Step 3 exit code: $LASTEXITCODE" | Out-File -FilePath $Log -Append
"=== Hermes bridge cycle end $(Get-Date) ===" | Out-File -FilePath $Log -Append
