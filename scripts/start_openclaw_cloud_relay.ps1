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

function Parse-RemoteUrl([string]$url) {
  if (-not $url) {
    return $null
  }
  $match = [regex]::Match($url.Trim(), '^wss?://(?<host>[^/:]+)(:(?<port>\d+))?')
  if (-not $match.Success) {
    return $null
  }
  $port = 80
  if ($url.StartsWith("wss://")) {
    $port = 443
  }
  if ($match.Groups["port"].Success) {
    $port = [int]$match.Groups["port"].Value
  }
  return @{
    host = $match.Groups["host"].Value
    port = $port
  }
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
    Start-Sleep -Milliseconds 500
  } catch {
    & taskkill /F /PID $processId | Out-Null
    Start-Sleep -Milliseconds 500
  }
}

$dotEnv = Read-DotEnv $envPath
$python = Get-Setting $dotEnv "CLAWEASE_PYTHON" (Join-Path $root ".conda\clawease\python.exe")
$script = Join-Path $root "scripts\openclaw_cloud_relay.py"
$listenHost = Get-Setting $dotEnv "OPENCLAW_CLOUD_LISTEN_HOST" "127.0.0.1"
$listenPort = [int](Get-Setting $dotEnv "OPENCLAW_CLOUD_LISTEN_PORT" "31879")
$remoteHost = Get-Setting $dotEnv "OPENCLAW_CLOUD_REMOTE_HOST" ""
$remotePort = [int](Get-Setting $dotEnv "OPENCLAW_CLOUD_REMOTE_PORT" "0")
$remoteUrl = Get-Setting $dotEnv "OPENCLAW_CLOUD_REMOTE_URL" ""
$pidFile = Get-Setting $dotEnv "OPENCLAW_CLOUD_RELAY_PID_FILE" (Join-Path $root ".openclaw-cloud-relay.pid")
$stdoutFile = Get-Setting $dotEnv "OPENCLAW_CLOUD_RELAY_STDOUT" (Join-Path $root ".openclaw-cloud-relay.out")
$stderrFile = Get-Setting $dotEnv "OPENCLAW_CLOUD_RELAY_STDERR" (Join-Path $root ".openclaw-cloud-relay.err")

$parsed = Parse-RemoteUrl $remoteUrl
if (-not $remoteHost -and $parsed) {
  $remoteHost = $parsed.host
}
if (($remotePort -le 0) -and $parsed) {
  $remotePort = $parsed.port
}
if (-not $remoteHost) {
  $remoteHost = "129.211.7.193"
}
if ($remotePort -le 0) {
  $remotePort = 31925
}

if (-not (Test-Path $python)) {
  throw "Missing Python runtime: $python"
}
if (-not (Test-Path $script)) {
  throw "Missing relay script: $script"
}

if (Test-Path $pidFile) {
  $oldPidRaw = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($oldPidRaw) {
    $oldPid = [int]$oldPidRaw
    if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) {
      Stop-ByPid $oldPid
    }
  }
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$listenerPid = Get-ListenerPid $listenPort
if ($listenerPid) {
  Stop-ByPid $listenerPid
}

$listenerPidAfterStop = Get-ListenerPid $listenPort
if ($listenerPidAfterStop) {
  throw "port $listenPort is still occupied by pid=$listenerPidAfterStop"
}

$proc = Start-Process `
  -FilePath $python `
  -ArgumentList $script, "--remote-host", $remoteHost, "--remote-port", $remotePort, "--listen-host", $listenHost, "--listen-port", $listenPort `
  -PassThru `
  -RedirectStandardOutput $stdoutFile `
  -RedirectStandardError $stderrFile `
  -WindowStyle Hidden

Set-Content -Path $pidFile -Value $proc.Id -Encoding ASCII
Start-Sleep -Seconds 2

if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) {
  $stderr = ""
  if (Test-Path $stderrFile) {
    $stderr = (Get-Content $stderrFile -Raw)
  }
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
  throw "relay process exited unexpectedly (pid=$($proc.Id)). stderr=$stderr"
}

$listenerPidNow = Get-ListenerPid $listenPort
if (-not $listenerPidNow) {
  Stop-ByPid $proc.Id
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
  throw "relay did not open listener on $listenHost`:$listenPort"
}
if ($listenerPidNow -ne $proc.Id) {
  Stop-ByPid $proc.Id
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
  throw "listener pid mismatch on $listenHost`:$listenPort (expected=$($proc.Id), actual=$listenerPidNow)"
}

$healthUrl = "http://$listenHost`:$listenPort/healthz"
try {
  $health = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 8
  if ($health.StatusCode -ne 200) {
    throw "status=$($health.StatusCode)"
  }
} catch {
  $msg = $_.Exception.Message
  Stop-ByPid $proc.Id
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
  throw "cloud gateway health check failed via relay ($healthUrl): $msg"
}

Write-Output "relay ready on ws://$listenHost`:$listenPort -> $remoteHost`:$remotePort (pid=$($proc.Id))"

