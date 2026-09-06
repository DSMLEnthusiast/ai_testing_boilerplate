#!/usr/bin/env pwsh
# MEAI Evaluation Runner
# Builds and runs the MEAI evaluation with Copilot SDK integration

param(
    [int]$Repetitions = 1,
    [string]$Output = "meai_results.json",
    [string]$Model = "gpt-4.1",
    [switch]$Build = $false,
    [switch]$NoBuild = $false
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$MeaiDir = Join-Path $RepoRoot "evals" "eval_dotnet"

Write-Host "MEAI Evaluation Runner" -ForegroundColor Green
Write-Host "Repository root: $RepoRoot"
Write-Host ""

# Set environment variables
$env:COPILOT_MODEL = $Model
$env:PYTHONPATH = Join-Path $RepoRoot "src"

Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Model: $($env:COPILOT_MODEL)"
Write-Host "  Python path: $($env:PYTHONPATH)"
Write-Host "  Repetitions: $Repetitions"
Write-Host "  Output: $Output"
Write-Host ""

# Build unless --NoBuild is specified
if (-not $NoBuild) {
    Write-Host "Building MEAI project..." -ForegroundColor Yellow
    Push-Location $MeaiDir
    try {
        dotnet build -c Release
        if ($LASTEXITCODE -ne 0) {
            throw "Build failed"
        }
    } finally {
        Pop-Location
    }
    Write-Host "Build successful" -ForegroundColor Green
    Write-Host ""
}

# Run evaluation
Write-Host "Running evaluation..." -ForegroundColor Yellow
Push-Location $RepoRoot
try {
    dotnet run --project $MeaiDir --no-build -- --repetitions $Repetitions --output $Output --provider copilot-sdk
    if ($LASTEXITCODE -ne 0) {
        throw "Evaluation failed"
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Evaluation complete. Results saved to: $Output" -ForegroundColor Green

# Display summary
if (Test-Path $Output) {
    Write-Host ""
    Write-Host "Results Summary:" -ForegroundColor Cyan
    $results = Get-Content $Output | ConvertFrom-Json
    $passed = @($results | Where-Object { $_.passed -eq $true }).Count
    $failed = @($results | Where-Object { $_.passed -eq $false }).Count
    $totalTime = ($results | Measure-Object -Property latency_ms -Sum).Sum

    Write-Host "  Total runs: $($results.Count)"
    Write-Host "  Passed: $passed"
    Write-Host "  Failed: $failed"
    Write-Host "  Total latency: $([Math]::Round($totalTime, 2))ms"
    Write-Host "  Average latency: $([Math]::Round($totalTime / $results.Count, 2))ms"
}
