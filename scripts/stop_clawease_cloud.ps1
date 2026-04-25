$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envPath = Join-Path $root ".env"

function Read-DotEnv([string]$path) {
  $map = @{}
  if (-not (Test-Path $path)) {
    return $map
  }
  foreach ($line in Get-Content $path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) {
      continue
    }
    $parts = $trimmed -split "=", 2
    if ($parts.Count -ne 2) {
      continue
    }
    $name = $parts[0].Trim()
    $value = $parts[1].Trim()
    if ((($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) -and $value.Length -ge 2) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    if ($name) {
      $map[$name] = $value
    }
  }
  return $map
}

function Get-Setting([hashtable]$dotEnv, [string]$name, [string]$fallback = "") {
  $fromProcess = [Environment]::GetEnvironmentVariable($name)
  if ($fromProcess) {
    return $fromProcess.Trim()
  }
  if ($dotEnv.ContainsKey($name)) {
    return ($dotEnv[$name] | Out-String).Trim()
  }
  return $fallback
}

function Get-ListenerPid([int]$port) {
  $line = netstat -ano | Select-String ":$port" | Where-Object { $_ -match "LISTENING" } | Select-Object -First 1
  if (-not $line) {
    return $null
  }
  $parts = ($line.ToString().Trim() -split '\s+')
  if ($parts.Count -lt 5) {
    return $null
  }
  return [int]$parts[-1]
}

function Stop-ByPid([int]$processId) {
  try {
    Stop-Process -Id $processId -Force -ErrorAction Stop
    Start-Sleep -Milliseconds 400
  } catch {
    & taskkill /F /PID $processId | Out-Null
    Start-Sleep -Milliseconds 400
  }
}

$dotEnv = Read-DotEnv $envPath
$pidFile = Get-Setting $dotEnv "OPENCLAW_CLOUD_RELAY_PID_FILE" (Join-Path $root ".openclaw-cloud-relay.pid")
$listenPort = [int](Get-Setting $dotEnv "OPENCLAW_CLOUD_LISTEN_PORT" "31879")

$stoppedAny = $false
if (Test-Path $pidFile) {
  $relayPidRaw = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($relayPidRaw) {
    $relayPid = [int]$relayPidRaw
    if (Get-Process -Id $relayPid -ErrorAction SilentlyContinue) {
      Stop-ByPid $relayPid
      $stoppedAny = $true
      Write-Output "[clawease-cloud] relay stopped by pid file (pid=$relayPid)"
    }
  }
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$listenerPid = Get-ListenerPid $listenPort
if ($listenerPid) {
  Stop-ByPid $listenerPid
  $stoppedAny = $true
  Write-Output "[clawease-cloud] relay stopped by port fallback (pid=$listenerPid, port=$listenPort)"
}

$listenerPidAfter = Get-ListenerPid $listenPort
if ($listenerPidAfter) {
  Write-Output "[clawease-cloud] failed to stop listener on port $listenPort (pid=$listenerPidAfter)"
  exit 1
}

if (-not $stoppedAny) {
  Write-Output "[clawease-cloud] relay was not running"
}

