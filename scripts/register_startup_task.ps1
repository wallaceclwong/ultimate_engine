$PYTHON  = "c:\Users\ASUS\ultimate_engine\.venv\Scripts\python.exe"
$WORKDIR = "c:\Users\ASUS\ultimate_engine"

Write-Host "=============================================="
Write-Host "  Ultimate Engine — Task Scheduler Setup"
Write-Host "=============================================="
Write-Host ""

# ── 1. Startup task (boot → racecards + war room) ──────────────────────────
$action1  = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument '/c "c:\Users\ASUS\ultimate_engine\scripts\lunar_startup.bat"' `
    -WorkingDirectory $WORKDIR

$trigger1 = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger1.Delay = "PT3M"   # 3-min grace for network + Tailscale

$settings1 = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 23) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -MultipleInstances IgnoreNew

$task1 = Register-ScheduledTask `
    -TaskName "UltimateEngine_Startup" `
    -Action $action1 `
    -Trigger $trigger1 `
    -Settings $settings1 `
    -Force

Write-Host "[1/3] UltimateEngine_Startup  → state: $($task1.State)"

# ── 2. Heartbeat (every 30 min → vitals + self-heal) ───────────────────────
$action2  = New-ScheduledTaskAction `
    -Execute $PYTHON `
    -Argument "scripts\lunar_heartbeat.py" `
    -WorkingDirectory $WORKDIR

$trigger2 = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 30) `
    -Once -At (Get-Date).Date   # starts today, repeats every 30 min forever

$settings2 = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew

$task2 = Register-ScheduledTask `
    -TaskName "UltimateEngine_Heartbeat" `
    -Action $action2 `
    -Trigger $trigger2 `
    -Settings $settings2 `
    -Force

Write-Host "[2/3] UltimateEngine_Heartbeat → state: $($task2.State)"

# ── 3. Morning odds refresh (09:30 HKT daily → scrape odds + patch Kelly) ──
#    The --odds mode guards itself: exits silently on non-race days.
$action3  = New-ScheduledTaskAction `
    -Execute $PYTHON `
    -Argument "ultimate_scheduler_vm.py --odds" `
    -WorkingDirectory $WORKDIR

$trigger3 = New-ScheduledTaskTrigger -Daily -At "09:30"

$settings3 = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

$task3 = Register-ScheduledTask `
    -TaskName "UltimateEngine_OddsRefresh" `
    -Action $action3 `
    -Trigger $trigger3 `
    -Settings $settings3 `
    -Force

Write-Host "[3/3] UltimateEngine_OddsRefresh → state: $($task3.State)"

Write-Host ""
Write-Host "=============================================="
Write-Host "  All tasks registered. Summary:"
Write-Host "    Startup      : At logon +3 min"
Write-Host "    Heartbeat    : Every 30 minutes"
Write-Host "    OddsRefresh  : Daily at 09:30 (race days only)"
Write-Host "=============================================="
