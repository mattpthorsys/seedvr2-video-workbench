param(
  [switch]$Full,
  [switch]$Frontend,
  [switch]$Docker
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}

Write-Host "Compiling backend and worker Python..."
& $Python -m compileall -q backend\app worker

if ($Full) {
  Write-Host "Running full backend test suite..."
  & $Python -m pytest backend\tests
} else {
  $ChangedFiles = @()
  try {
    $ChangedFiles = @(git diff --name-only HEAD)
  } catch {
    $ChangedFiles = @()
  }

  $SelectedTests = [System.Collections.Generic.List[string]]::new()
  function Add-Test([string]$Path) {
    if (-not $SelectedTests.Contains($Path)) {
      [void]$SelectedTests.Add($Path)
    }
  }

  foreach ($File in $ChangedFiles) {
    switch -Wildcard ($File) {
      "backend/app/jobs.py" { Add-Test "backend/tests/test_jobs.py" }
      "backend/app/model_downloads.py" { Add-Test "backend/tests/test_model_downloads.py" }
      "backend/app/model_check.py" { Add-Test "backend/tests/test_model_check.py" }
      "backend/app/file_browser.py" { Add-Test "backend/tests/test_file_browser.py" }
      "backend/app/video_probe.py" { Add-Test "backend/tests/test_video_probe.py" }
      "backend/app/eta.py" { Add-Test "backend/tests/test_eta.py" }
      "backend/app/pipeline/encode.py" { Add-Test "backend/tests/test_encode.py" }
      "backend/app/pipeline/seedvr2.py" { Add-Test "backend/tests/test_seedvr2_adapter.py" }
      "backend/app/pipeline/stats.py" { Add-Test "backend/tests/test_stats.py" }
    }
  }

  if ($SelectedTests.Count -gt 0) {
    Write-Host "Running focused backend tests for current changes..."
    $TestArgs = @($SelectedTests.ToArray())
    & $Python -m pytest @TestArgs
  } else {
    Write-Host "No mapped backend tests for the current diff."
  }
}

if ($Frontend -or $Full) {
  Write-Host "Building frontend..."
  Push-Location frontend
  try {
    npm.cmd run build
  } finally {
    Pop-Location
  }
}

if ($Docker) {
  Write-Host "Checking Docker Compose test configuration..."
  docker compose --profile test config --quiet
}
