# Runs the complete data-preparation pipeline in order. Stops at the first failing step.
# Usage (from the data_preparation folder, with the virtual environment activated):
#   .\run_pipeline.ps1                  # keeps the existing raw dataset
#   .\run_pipeline.ps1 -RegenerateRaw   # regenerates the raw dataset (same seed -> identical file)
#   .\run_pipeline.ps1 -SkipNotebooks   # skip executing the four notebooks
param([switch]$RegenerateRaw, [switch]$SkipNotebooks)

# "Continue", not "Stop": Windows PowerShell 5.1 turns any stderr line of a native program (e.g. the Jupyter
# kernel's harmless "running over TCP" notice) into a terminating error. Success is judged by exit codes below.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$env:PYTHONDONTWRITEBYTECODE = "1"
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

$steps = @(
    @{ name = "1/7 generate raw dataset";     args = @("scripts\generate_dataset.py") + $(if ($RegenerateRaw) { "--force" } else { @() }) },
    @{ name = "2/7 data quality assessment";  args = @("scripts\data_quality_analysis.py") },
    @{ name = "3/7 cleaning";                 args = @("scripts\clean_dataset.py") },
    @{ name = "4/7 preprocessing";            args = @("scripts\preprocess_dataset.py") },
    @{ name = "5/7 exploratory analysis";     args = @("scripts\exploratory_analysis.py") },
    @{ name = "6/7 validation";               args = @("scripts\validate_dataset.py") }
)
if (-not $SkipNotebooks) {
    $steps += @{ name = "7/7 execute notebooks"; args = @("scripts\build_notebooks.py") }
}

foreach ($s in $steps) {
    Write-Host "== $($s.name)" -ForegroundColor Cyan
    & $python -B @($s.args)
    if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: $($s.name)" -ForegroundColor Red; exit $LASTEXITCODE }
}
Write-Host "Pipeline finished. Reports are in .\reports, figures in .\visualizations." -ForegroundColor Green
