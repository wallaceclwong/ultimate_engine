@echo off
setlocal

:: Get the directory where the script is located
set "BASE_DIR=%~dp0.."
pushd "%BASE_DIR%"

set "PYTHON_EXE=%BASE_DIR%\.venv\Scripts\python.exe"
set "HEARTBEAT_SCRIPT=%BASE_DIR%\scripts\lunar_heartbeat.py"
set "TASK_NAME=UltimateEngine_Heartbeat"

echo ======================================================
echo Ultimate Engine: Watchdog Automation Setup
echo ======================================================
echo.
echo This script will register the Lunar Heartbeat with 
echo Windows Task Scheduler to run every 30 minutes.
echo.

:: Check if python exists
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python environment not found at: %PYTHON_EXE%
    echo Please ensure the project is correctly installed.
    pause
    exit /b 1
)

:: Create the scheduled task
:: /sc minute /mo 30 - Every 30 minutes
:: /tn - Task Name
:: /tr - Task Run (the command)
:: /f - Force (overwrite existing)
echo [SYSTEM] Registering task: %TASK_NAME%
schtasks /create /tn "%TASK_NAME%" /tr "\"%PYTHON_EXE%\" \"%HEARTBEAT_SCRIPT%\"" /sc minute /mo 30 /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Watchdog registered successfully!
    echo The Ultimate Engine will now self-heal every 30 minutes.
) else (
    echo.
    echo [ERROR] Failed to register task. Try running this script as Administrator.
)

popd
pause
