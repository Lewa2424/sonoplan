# Host readiness for STG-01 SPPS build (Windows developer machine).
# Primary SPPS path is GitHub Actions / remote Linux — not local Docker Desktop.
$ErrorActionPreference = "Continue"
Write-Host "=== SonoPlan STG-01 environment check ==="
Write-Host "Date: $(Get-Date -Format o)"
Write-Host "Python: $(python --version 2>&1)"
Write-Host "Git: $(git --version 2>&1)"
Write-Host "Primary SPPS build: GitHub Actions / remote Linux (see docs/engine-build-without-docker.md)"
Write-Host "Local Docker Desktop: expected BLOCKED on Windows 19044 without OS update"

$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
  Write-Host "Docker: $(docker --version 2>&1)"
} else {
  Write-Host "Docker: NOT FOUND (OK for STG-02; use CI/VPS for STG-01 binary)"
}

Write-Host "WSL status:"
wsl --status 2>&1 | Out-String | Write-Host

$pin = Get-Content (Join-Path $PSScriptRoot "..\PINNED.json") -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Host "Pinned I-Simpa: $($pin.isimpa.commit)"
Write-Host "primary_build_path: $($pin.primary_build_path)"
Write-Host "local_docker_desktop: $($pin.local_docker_desktop)"
Write-Host "Recorded build_status: $($pin.build_status)"
Write-Host "Recorded blocker: $($pin.build_blocker)"
Write-Host "binary_checksum: $($pin.binary_checksum)"
