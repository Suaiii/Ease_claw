$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".conda\clawease\python.exe"
$server = Join-Path $root "scripts\demo_server.py"

if (-not (Test-Path $python)) {
    throw "Missing Python runtime: $python"
}

if (-not (Test-Path $server)) {
    throw "Missing demo server: $server"
}

& $python $server --host 127.0.0.1 --port 8765
