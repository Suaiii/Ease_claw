$ErrorActionPreference = "Stop"

$root = "E:\aNB\Ease-claw"
$configPath = "C:\Users\ZHUyi\.openclaw\openclaw.json"
$workspace = Join-Path $root "openclaw\clawease-intent-workspace"
$python = Join-Path $root ".conda\clawease\python.exe"
$installer = Join-Path $root "scripts\install_clawease_parser_agent.py"

if (!(Test-Path $configPath)) {
  throw "OpenClaw config not found: $configPath"
}
if (!(Test-Path $workspace)) {
  throw "Parser workspace not found: $workspace"
}
if (!(Test-Path $installer)) {
  throw "Installer script not found: $installer"
}
if (!(Test-Path $python)) {
  $python = "python"
}

& $python $installer
if ($LASTEXITCODE -ne 0) {
  throw "Parser agent install failed"
}
Write-Output "[clawease-parser] next step: set OPENCLAW_CLOUD_AGENT_ID=clawease-intent on any gateway that has this agent config"
