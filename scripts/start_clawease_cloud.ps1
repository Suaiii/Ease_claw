$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $root ".conda\clawease\python.exe"
$voice = Join-Path $root "scripts\voice_to_action.py"
$relay = Join-Path $root "scripts\start_openclaw_cloud_relay.ps1"
$helper = Join-Path $root "scripts\openclaw_cloud_intent.mjs"

if (-not (Test-Path $python)) {
  throw "Missing Python runtime: $python"
}
if (-not (Test-Path $voice)) {
  throw "Missing voice entry: $voice"
}
if (-not (Test-Path $relay)) {
  throw "Missing relay script: $relay"
}
if (-not (Test-Path $helper)) {
  throw "Missing cloud helper: $helper"
}

Write-Output "[clawease-cloud] starting relay..."
& $relay
if ($LASTEXITCODE -ne 0) {
  throw "relay startup failed"
}

if (-not $env:OPENCLAW_PARSE_MODE) {
  $env:OPENCLAW_PARSE_MODE = "openclaw_cloud"
}
if (-not $env:OPENCLAW_CLOUD_STATE_DIR) {
  $env:OPENCLAW_CLOUD_STATE_DIR = Join-Path $root ".openclaw-cloud"
}
if (-not $env:OPENCLAW_CLOUD_URL) {
  $env:OPENCLAW_CLOUD_URL = "ws://127.0.0.1:31879"
}

Write-Output "[clawease-cloud] probing cloud gateway RPC..."
$probe = & node $helper "请只回复OK" 2>&1
if ($LASTEXITCODE -ne 0) {
  throw "cloud helper probe failed: $($probe | Out-String)"
}
$probeText = ($probe | Out-String).Trim()
if (-not $probeText) {
  throw "cloud helper probe returned empty output"
}
Write-Output "[clawease-cloud] probe reply: $probeText"

$strictRaw = ($env:CLAWEASE_STRICT_PARSER_CHECK | Out-String).Trim().ToLower()
$strictParserCheck = $strictRaw -in @("1", "true", "yes", "on")
if ($strictParserCheck) {
  Write-Output "[clawease-cloud] strict parser check enabled, running dry-run..."
  & $python $voice --voice-text "给10086打电话" --dry-run
  if ($LASTEXITCODE -ne 0) {
    throw "voice_to_action dry-run failed"
  }
}

Write-Output ""
Write-Output "[clawease-cloud] ready"
Write-Output "[clawease-cloud] examples:"
Write-Output "  $python $voice --voice-text \"给10086打电话\""
Write-Output "  $python $voice --voice-text \"给12306发一条我晚点到\""
Write-Output "  $python $voice --voice-text \"有没有新短信\" --no-tts"
Write-Output "[clawease-cloud] optional: set CLAWEASE_STRICT_PARSER_CHECK=1 to run startup dry-run"
