@echo off
:: HKJC AI — Boot Startup Script (v3)
:: Registered as Windows logon task via Task Scheduler.
:: Step 1: pc_startup.py  — scrape racecards, sync VM, trigger predictions
:: Step 2: ultimate_scheduler_vm.py --live  — war room (runs all day)

echo ============================================
echo  HKJC AI — Boot Startup
echo  %date% %time%
echo ============================================

:: 1. Ensure Tailscale is running (silent, tolerates failure)
echo [1/4] Checking Tailscale...
powershell -Command "try { if ((Get-Service -Name 'Tailscale').Status -ne 'Running') { Start-Service -Name 'Tailscale' } } catch {}"

:: 2. Wait 20s for network + Tailscale tunnel to stabilize
echo [2/4] Waiting for network...
timeout /t 20 /nobreak > nul

:: 3. PC Startup — scrape racecards, sync to VM, trigger AI predictions
echo [3/4] Running PC startup orchestrator...
cd /d c:\Users\ASUS\ultimate_engine
c:\Users\ASUS\ultimate_engine\.venv\Scripts\python.exe scripts\pc_startup.py >> logs\startup.log 2>&1

:: 4. Launch the War Room scheduler (DETACHED — closing this window won't kill it)
echo [4/4] Launching War Room (Live Mode, detached)...
start "UltimateEngine_WarRoom" /MIN c:\Users\ASUS\ultimate_engine\.venv\Scripts\python.exe ultimate_scheduler_vm.py --live
echo [OK] War Room launched in background. This window can be closed safely.
timeout /t 3 /nobreak > nul
