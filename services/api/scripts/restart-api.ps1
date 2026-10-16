# Restart local SonoPlan API on 127.0.0.1:8000 without --reload.
# Windows WatchFiles/--reload leaves orphan multiprocessing children that hold the port
# after the parent is killed; health then flakes and the web UI falls to offline/mock.
#
# Usage (from repo root or services/api):
#   powershell -File services/api/scripts/restart-api.ps1

$ErrorActionPreference = "Stop"
$ApiRoot = Split-Path -Parent $PSScriptRoot
$Port = 8000
$HostAddr = "127.0.0.1"

function Stop-PortHolders {
  $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  foreach ($c in $conns) {
    $ownerPid = $c.OwningProcess
    if ($ownerPid -and $ownerPid -gt 0) {
      Write-Host "Stopping listener PID $ownerPid"
      Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
    }
  }

  # Orphans from uvicorn --reload / multiprocessing.spawn (parent already gone).
  $spawn = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
      $_.CommandLine -and (
        $_.CommandLine -match "sonoplan_api\.main:app" -or
        $_.CommandLine -match "multiprocessing\.spawn" -or
        ($_.CommandLine -match "uvicorn" -and $_.CommandLine -match "8000")
      )
    }
  foreach ($p in $spawn) {
    Write-Host "Stopping related PID $($p.ProcessId)"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
  }

  Start-Sleep -Seconds 1
}

Stop-PortHolders

$still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($still) {
  $ids = ($still.OwningProcess | Select-Object -Unique) -join ", "
  throw "Port $Port still in use by PID(s): $ids"
}

$Uvicorn = Join-Path $ApiRoot ".venv\Scripts\uvicorn.exe"
if (-not (Test-Path $Uvicorn)) {
  throw "Missing $Uvicorn - create venv and pip install -e .[dev] first."
}

Write-Host "Starting API (no --reload) on http://${HostAddr}:${Port}"
Set-Location $ApiRoot
& $Uvicorn "sonoplan_api.main:app" --app-dir src --host $HostAddr --port $Port
