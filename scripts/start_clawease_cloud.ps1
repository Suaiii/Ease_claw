$ErrorActionPreference = "Stop"

$root = "E:\aNB\Ease-claw"
$python = Join-Path $root ".conda\clawease\python.exe"
$voice = Join-Path $root "scripts\voice_to_action.py"
$relay = Join-Path $root "scripts\start_openclaw_cloud_relay.ps1"

Write-Output "[clawease-cloud] starting relay..."
powershell -ExecutionPolicy Bypass -File $relay | Out-Host

Write-Output "[clawease-cloud] verifying cloud intent path..."
$env:OPENCLAW_PARSE_MODE = "openclaw_cloud"
$env:OPENCLAW_CLOUD_STATE_DIR = "E:\aNB\Ease-claw\.openclaw-cloud"
$env:OPENCLAW_CLOUD_URL = "ws://127.0.0.1:31879"

& $python $voice --voice-text "给10086打电话" --dry-run

Write-Output ""
Write-Output "[clawease-cloud] ready"
Write-Output "[clawease-cloud] examples:"
Write-Output "  $python $voice --voice-text ""给10086打电话"""
Write-Output "  $python $voice --voice-text ""给12306发一条我晚点到"""
Write-Output "  $python $voice --voice-text ""有没有新短信"" --no-tts"
