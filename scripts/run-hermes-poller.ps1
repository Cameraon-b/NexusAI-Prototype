$Project = "C:\FilesForNora\NexusAI"
$LogDir = "$Project\logs"
$Log = "$LogDir\hermes-poller.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $Project

python "$Project\scripts\nexusai_agent_worker.py" `
  --base-url "http://127.0.0.1:5055" `
  --agent "Hermes" `
  --ack `
  --auto-reply *>> $Log
