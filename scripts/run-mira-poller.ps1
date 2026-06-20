$Project = "C:\Path\To\NexusAI"
$LogDir = "$Project\logs"
$Log = "$LogDir\mira-poller.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $Project

python "$Project\scripts\nexusai_agent_worker.py" `
  --base-url "http://192.168.1.134:5055" `
  --agent "Mira" `
  --ack `
  --auto-reply *>> $Log
