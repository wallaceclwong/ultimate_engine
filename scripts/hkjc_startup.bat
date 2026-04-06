@echo off
:: HKJC Race Day Startup Script
:: Runs on PC boot — checks if it's a race day, scrapes racecards,
:: syncs to VM, triggers predictions, and starts live odds monitoring.

echo ============================================
echo  HKJC AI — Startup Check
echo  %date% %time%
echo ============================================

:: Wait 30s for network to be ready
timeout /t 30 /nobreak > nul

:: Run the orchestrator
cd /d c:\Users\ASUS\ultimate_engine
c:\Users\ASUS\ultimate_engine\.venv\Scripts\python.exe scripts\pc_startup.py

pause
