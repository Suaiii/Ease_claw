$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$cloud = Join-Path $root "scripts\start_clawease_cloud.ps1"
$demo = Join-Path $root "start_demo.ps1"

if (-not (Test-Path $cloud)) {
  throw "Missing cloud startup script: $cloud"
}

if (-not (Test-Path $demo)) {
  throw "Missing demo startup script: $demo"
}

Write-Output "[clawease] booting cloud intent path..."
& $cloud

Write-Output ""
Write-Output "[clawease] starting web demo on http://127.0.0.1:8765 ..."
& $demo
