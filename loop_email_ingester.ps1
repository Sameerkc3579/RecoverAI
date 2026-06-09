# ===============================================================================
# RecoverAI - Continuous Email Ingester Background Worker
# ===============================================================================
# This script will continuously run the email ingester every 15 minutes.
# Keep this PowerShell window open to ensure emails are ingested.
# ===============================================================================

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython  = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$IntervalMinutes = 15

if (-not (Test-Path $VenvPython)) {
    Write-Host "Virtual environment not found at $VenvPython" -ForegroundColor Red
    Write-Host "Please ensure you have run 'python -m venv .venv' and installed requirements." -ForegroundColor Red
    Pause
    exit 1
}

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  RecoverAI Continuous Email Worker Started" -ForegroundColor Cyan
Write-Host "  Checking Inbox every $IntervalMinutes minutes..." -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

while ($true) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] Waking up to check emails..." -ForegroundColor Yellow
    
    # Run the email ingester
    $Process = Start-Process `
        -FilePath $VenvPython `
        -ArgumentList "-m", "app.workers.email_ingester" `
        -WorkingDirectory $ProjectRoot `
        -NoNewWindow `
        -Wait `
        -PassThru
    
    if ($Process.ExitCode -eq 0) {
        Write-Host "[$timestamp] Cycle completed successfully." -ForegroundColor Green
    } else {
        Write-Host "[$timestamp] Cycle exited with an error code: $($Process.ExitCode)." -ForegroundColor Red
    }

    Write-Host "Going to sleep for $IntervalMinutes minutes. (Press Ctrl+C to stop)`n" -ForegroundColor DarkGray
    Start-Sleep -Seconds ($IntervalMinutes * 60)
}
