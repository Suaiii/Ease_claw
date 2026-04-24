param(
  [string]$OpenClawImage = 'ghcr.io/openclaw/openclaw:latest',
  [string]$GatewayBind = 'loopback',
  [string]$Timezone = 'Asia/Shanghai'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$configDir = Join-Path $repoRoot '.openclaw-config'
$workspaceDir = Join-Path $repoRoot 'workspace'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw 'Docker is not installed or not in PATH. Install Docker Desktop first.'
}

if (-not (Get-Command bash -ErrorAction SilentlyContinue)) {
  throw 'bash is not available. Install Git for Windows (Git Bash) or WSL.'
}

New-Item -ItemType Directory -Force -Path $configDir | Out-Null
New-Item -ItemType Directory -Force -Path $workspaceDir | Out-Null

$env:OPENCLAW_IMAGE = $OpenClawImage
$env:OPENCLAW_GATEWAY_BIND = $GatewayBind
$env:OPENCLAW_SANDBOX = '1'
$env:OPENCLAW_CONFIG_DIR = $configDir -replace '\\','/'
$env:OPENCLAW_WORKSPACE_DIR = $workspaceDir -replace '\\','/'
$env:OPENCLAW_TZ = $Timezone

Write-Host "OPENCLAW_IMAGE=$($env:OPENCLAW_IMAGE)"
Write-Host "OPENCLAW_GATEWAY_BIND=$($env:OPENCLAW_GATEWAY_BIND)"
Write-Host "OPENCLAW_SANDBOX=$($env:OPENCLAW_SANDBOX)"
Write-Host "OPENCLAW_CONFIG_DIR=$($env:OPENCLAW_CONFIG_DIR)"
Write-Host "OPENCLAW_WORKSPACE_DIR=$($env:OPENCLAW_WORKSPACE_DIR)"
Write-Host "OPENCLAW_TZ=$($env:OPENCLAW_TZ)"

Push-Location $repoRoot
try {
  bash ./scripts/docker/setup.sh
}
finally {
  Pop-Location
}
