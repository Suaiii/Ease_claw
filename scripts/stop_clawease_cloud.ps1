$ErrorActionPreference = "Stop"

$pidFile = "E:\aNB\Ease-claw\.openclaw-cloud-relay.pid"

if (!(Test-Path $pidFile)) {
  Write-Output "[clawease-cloud] relay pid file not found"
  exit 0
}

$pid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
if (!$pid) {
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
  Write-Output "[clawease-cloud] empty pid file removed"
  exit 0
}

$proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
if ($proc) {
  try {
    $proc.Kill()
    $proc.WaitForExit()
    Write-Output "[clawease-cloud] relay stopped (pid=$pid)"
  } catch {
    Write-Output "[clawease-cloud] failed to stop relay cleanly: $($_.Exception.Message)"
    exit 1
  }
} else {
  Write-Output "[clawease-cloud] relay process not running"
}

Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
