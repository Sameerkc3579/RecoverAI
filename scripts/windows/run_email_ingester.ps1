# ===============================================================================
# RecoverAI - Email Ingester Task Runner
# ===============================================================================
# This script is called by Windows Task Scheduler every 15 minutes.
# It activates the project virtual environment and runs the email ingester.
#
# Usage (manual):
#   powershell -ExecutionPolicy Bypass -File scripts\windows\run_email_ingester.ps1
# ===============================================================================

# -- Configuration -------------------------------------------------------------
# Scripts live in scripts\windows\ — the project root is two levels up
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$LogDir      = Join-Path $ProjectRoot "logs"
$LogFile     = Join-Path $LogDir "email_ingester_$(Get-Date -Format 'yyyy-MM-dd').log"
$VenvPython  = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

# -- Ensure log directory exists ------------------------------------------------
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

# -- Helper: timestamped log writer --------------------------------------------
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
    $line = "$ts | $($Level.PadRight(8)) | run_email_ingester.ps1 - $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

Write-Log "=== RecoverAI Email Ingester - START ==="
Write-Log "Project root : $ProjectRoot"
Write-Log "Log file     : $LogFile"
Write-Log "Python       : $VenvPython"

# -- Verify virtual environment exists -----------------------------------------
if (-not (Test-Path $VenvPython)) {
    Write-Log "Virtual environment not found at $VenvPython" "ERROR"
    Write-Log "Run: python -m venv .venv && .venv\Scripts\pip install -r requirements.txt" "ERROR"
    exit 1
}

# -- Run the ingester ----------------------------------------------------------
Write-Log "Launching email_ingester.py ..."

$Process = Start-Process `
    -FilePath $VenvPython `
    -ArgumentList "-m", "app.workers.email_ingester" `
    -WorkingDirectory $ProjectRoot `
    -NoNewWindow `
    -Wait `
    -PassThru `
    -RedirectStandardOutput (Join-Path $LogDir "ingester_stdout.tmp") `
    -RedirectStandardError  (Join-Path $LogDir "ingester_stderr.tmp")

# -- Capture and append subprocess output to the daily log ---------------------
$stdout_file = Join-Path $LogDir "ingester_stdout.tmp"
$stderr_file = Join-Path $LogDir "ingester_stderr.tmp"

if (Test-Path $stdout_file) {
    Get-Content $stdout_file | ForEach-Object { Add-Content -Path $LogFile -Value $_ }
    Remove-Item $stdout_file -ErrorAction SilentlyContinue
}
if (Test-Path $stderr_file) {
    $stderrContent = Get-Content $stderr_file
    if ($stderrContent) {
        $stderrContent | ForEach-Object { Add-Content -Path $LogFile -Value "STDERR | $_" }
    }
    Remove-Item $stderr_file -ErrorAction SilentlyContinue
}

# -- Report exit code ----------------------------------------------------------
if ($Process.ExitCode -eq 0) {
    Write-Log "Email ingester completed successfully (exit 0)"
} else {
    Write-Log "Email ingester exited with code $($Process.ExitCode)" "WARN"
}

Write-Log "=== RecoverAI Email Ingester - END   ==="
