$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$cloudStop = Join-Path $root "scripts\stop_clawease_cloud.ps1"

if (-not (Test-Path $cloudStop)) {
  throw "Missing cloud stop script: $cloudStop"
}

& $cloudStop
