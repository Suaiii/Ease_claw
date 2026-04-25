$ErrorActionPreference = "Stop"

$python = "E:\aNB\Ease-claw\.conda\clawease\python.exe"
$script = "E:\aNB\Ease-claw\scripts\openclaw_cloud_relay.py"
$listenHost = "127.0.0.1"
$listenPort = 31879
$remoteHost = "129.211.7.193"
$remotePort = 31925
$pidFile = "E:\aNB\Ease-claw\.openclaw-cloud-relay.pid"
$stdoutFile = "E:\aNB\Ease-claw\.openclaw-cloud-relay.out"
$stderrFile = "E:\aNB\Ease-claw\.openclaw-cloud-relay.err"

if (Test-Path $pidFile) {
  $oldPid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($oldPid) {
    $oldProc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
    if ($oldProc) {
      try {
        $oldProc.Kill()
        $oldProc.WaitForExit()
      } catch {
      }
    }
  }
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
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

$client = New-Object System.Net.Sockets.TcpClient
try {
  $iar = $client.BeginConnect($listenHost, $listenPort, $null, $null)
  if (-not $iar.AsyncWaitHandle.WaitOne(3000)) {
    throw "relay did not open $listenHost`:$listenPort"
  }
  $client.EndConnect($iar) | Out-Null
  Write-Output "relay ready on ws://$listenHost`:$listenPort -> $remoteHost`:$remotePort (pid=$($proc.Id))"
} finally {
  $client.Close()
}
