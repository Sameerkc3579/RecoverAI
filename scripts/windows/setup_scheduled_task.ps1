# ===============================================================================
# RecoverAI - Register Windows Scheduled Task (Run as Administrator)
# ===============================================================================
#
# Creates a Windows Task Scheduler job that runs the email ingester every
# 15 minutes, indefinitely, using the project's virtual environment.
#
# PREREQUISITES:
#   1. Run this script as Administrator (right-click -> "Run as administrator")
#   2. Your .env must have IMAP_USER and IMAP_PASSWORD configured.
#   3. The virtual environment at .venv must exist and have all dependencies.
#
# Run once:
#   powershell -ExecutionPolicy Bypass -File scripts\windows\setup_scheduled_task.ps1
#
# To remove the task:
#   Unregister-ScheduledTask -TaskName "RecoverAI-EmailIngester" -Confirm:$false
# ===============================================================================

$TaskName   = "RecoverAI-EmailIngester"
# Scripts live in scripts\windows\ — the project root is two levels up
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ScriptPath  = Join-Path $PSScriptRoot "run_email_ingester.ps1"
$LogPath     = Join-Path $ProjectRoot "logs\scheduled_task_setup.log"

# -- Ensure log directory exists ------------------------------------------------
$LogDir = Split-Path $LogPath
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
    $line = "$ts | setup_scheduled_task.ps1 - $Message"
    Write-Host $line
    Add-Content -Path $LogPath -Value $line
}

Write-Log "=== Setting up Windows Scheduled Task ==="
Write-Log "Task name   : $TaskName"
Write-Log "Script path : $ScriptPath"

# -- Check admin privileges -----------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    Write-Log "ERROR: This script must be run as Administrator."
    Write-Host "`n!  Please right-click PowerShell -> 'Run as administrator' and try again." -ForegroundColor Red
    exit 1
}

# -- Verify the runner script exists -------------------------------------------
if (-not (Test-Path $ScriptPath)) {
    Write-Log "ERROR: Runner script not found: $ScriptPath"
    exit 1
}

# -- Remove existing task if present -------------------------------------------
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Log "Removing existing task '$TaskName' ..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Log "Existing task removed."
}

# -- Build task components ------------------------------------------------------

# Action: PowerShell running the runner script
$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -NonInteractive -File `"$ScriptPath`"" `
    -WorkingDirectory $ProjectRoot

# Trigger: Every 15 minutes, starting now, repeating indefinitely
$StartTime = (Get-Date).AddMinutes(1)   # Start 1 minute from now
$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At $StartTime `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

# Settings: Run whether user is logged on or not, with restart on failure
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Principal: Run as current user (SYSTEM for truly headless; adjust if needed)
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType S4U `
    -RunLevel Highest

# -- Register the task ----------------------------------------------------------
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "RecoverAI: Zero-touch email invoice ingestion - runs every 15 minutes" `
        -Force | Out-Null

    Write-Log "OK:  Scheduled task '$TaskName' registered successfully."
    Write-Host "`nOK:  Task '$TaskName' registered - runs every 15 minutes." -ForegroundColor Green
    Write-Host "    Next run: $($StartTime.ToString('HH:mm:ss'))" -ForegroundColor Cyan
    Write-Host "    View in: Task Scheduler -> Task Scheduler Library -> '$TaskName'" -ForegroundColor Cyan
    Write-Host "    To remove: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor Yellow

} catch {
    Write-Log "ERROR registering task: $_"
    Write-Host "`nERROR:  Failed to register task: $_" -ForegroundColor Red
    exit 1
}

Write-Log "=== Setup complete ==="
